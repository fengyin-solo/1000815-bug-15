"""集卡调度业务规则：状态流转、字段校验与筛选口径都收在这里。

派车链路：待派车 →（派车，司机与计划装卸时间落库）→ 已派车
        →（司机接单）→ 作业中 →（司机完单）→ 已完成。
已派车可以退回待派车，退回不清空已填的司机与计划信息；
同一集卡、同一作业任务在途期间不允许重复派车。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "truck"
REQUIRED_FIELDS = ["调度单号", "集卡牌号", "作业任务"]
DISPATCH_REQUIRED = ["司机姓名", "计划装卸时间"]
DISPATCH_FIELDS = ["司机姓名", "计划装卸时间", "所属车队", "作业任务", "集卡牌号"]
STATUS_ORDER = ["待派车", "已派车", "作业中", "已完成", "已取消"]
ACTIVE_STATUSES = {"已派车", "作业中"}
FINAL_STATUSES = {"已完成", "已取消"}
# 动作 → (允许执行的当前状态, 目标状态)；不在允许状态里的一律拦下
ACTION_TRANSITIONS = {
    "派车": ({"待派车"}, "已派车"),
    "接单": ({"已派车"}, "作业中"),
    "完单": ({"作业中"}, "已完成"),
    "退回": ({"已派车"}, "待派车"),
    "取消调度": ({"待派车", "已派车"}, "已取消"),
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class TruckService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("调度单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def driver_tasks(self, driver: str) -> list[dict[str, Any]]:
        """司机端任务列表：按司机姓名取回派给他的调度单，与调度列表读同一份台账。"""
        name = driver.strip()
        rows = [row for row in store.rows(MODULE) if str(row.get("司机姓名", "")).strip() == name]
        return sorted(rows, key=lambda row: int(row.get("id", 0)))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        rows = store.rows(MODULE)
        order_no = str(values.get("调度单号", "")).strip()
        if any(str(row.get("调度单号", "")).strip() == order_no for row in rows):
            return None, f"调度单号 {order_no} 已存在，台账里不能重复登记同一条调度单"
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + DISPATCH_FIELDS + ["派车时间", "返回时间"]:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        self._set_status(entry, "待派车")
        entry["abnormal"] = False
        rows.append(entry)
        return entry, "集卡调度单已登记"

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"集卡调度单 {entry_id} 不存在或已归档"
        if action not in ACTION_TRANSITIONS:
            return None, f"动作「{action}」不属于集卡调度可执行范围"
        allowed, target = ACTION_TRANSITIONS[action]
        current = str(entry.get("status", ""))
        if current not in allowed:
            return None, f"调度单当前状态「{current}」不能执行「{action}」"
        values = values or {}
        handler = {
            "派车": self._dispatch,
            "接单": self._accept,
            "完单": self._complete,
            "退回": self._return,
            "取消调度": self._cancel,
        }[action]
        return handler(entry, values)

    def _dispatch(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        # 派车信息落库：只覆盖本次提交的非空字段，退回重派时原有填写内容仍在
        for field in DISPATCH_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        missing = [field for field in DISPATCH_REQUIRED if not str(entry.get(field) or "").strip()]
        if missing:
            return None, f"派车前请先补齐：{'、'.join(missing)}"
        conflict = self._find_active_conflict(entry)
        if conflict is not None:
            return None, conflict
        entry["派车时间"] = str(values.get("派车时间") or "").strip() or _now()
        entry.pop("返回时间", None)
        self._set_status(entry, "已派车")
        return entry, f"已派车：{entry['集卡牌号']}（司机 {entry['司机姓名']}），等待司机接单"

    def _accept(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        mismatch = self._driver_mismatch(entry, values, "接单")
        if mismatch:
            return None, mismatch
        self._set_status(entry, "作业中")
        return entry, f"司机 {entry.get('司机姓名', '')} 已接单，集卡作业中"

    def _complete(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        mismatch = self._driver_mismatch(entry, values, "完单")
        if mismatch:
            return None, mismatch
        entry["返回时间"] = str(values.get("返回时间") or "").strip() or _now()
        self._set_status(entry, "已完成")
        return entry, f"调度单 {entry.get('调度单号', '')} 已完单"

    def _return(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        # 退回只回退状态，司机姓名、计划装卸时间等已填信息保留，重派时直接带出
        self._set_status(entry, "待派车")
        return entry, "已退回待派车，原司机与计划装卸时间已保留，可直接重派"

    def _cancel(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        self._set_status(entry, "已取消")
        return entry, f"调度单 {entry.get('调度单号', '')} 已取消"

    def _find_active_conflict(self, entry: dict[str, Any]) -> str | None:
        """重复派车拦截：同一集卡在途、或同一作业任务已派给别的车，都不许再派。"""
        plate = str(entry.get("集卡牌号", "")).strip()
        task = str(entry.get("作业任务", "")).strip()
        for row in store.rows(MODULE):
            if row is entry or row.get("status") not in ACTIVE_STATUSES:
                continue
            if plate and str(row.get("集卡牌号", "")).strip() == plate:
                return f"集卡 {plate} 还有进行中的调度单 {row.get('调度单号', '')}，重复派车已拦截"
            if task and str(row.get("作业任务", "")).strip() == task:
                return f"作业任务「{task}」已派给集卡 {row.get('集卡牌号', '')}，不能重复派车"
        return None

    def _driver_mismatch(self, entry: dict[str, Any], values: dict[str, Any], action: str) -> str | None:
        claimed = str(values.get("司机姓名") or "").strip()
        assigned = str(entry.get("司机姓名", "")).strip()
        if claimed and assigned and claimed != assigned:
            return f"该调度单已派给 {assigned}，{claimed} 不能{action}"
        return None

    def _set_status(self, entry: dict[str, Any], status: str) -> None:
        entry["status"] = status
        entry["调度状态"] = status  # 台账列与接口状态保持一致
        entry["pending"] = status not in FINAL_STATUSES
