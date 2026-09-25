"""集卡调度业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "truck"
REQUIRED_FIELDS = ["调度单号", "集卡牌号", "司机姓名"]
# 调度单上允许登记与展示的字段；创建时全部保留，不再只留必填三项
ENTRY_FIELDS = ["调度单号", "集卡牌号", "司机姓名", "作业任务", "计划装卸时间", "派车时间", "返回时间", "所属车队"]
STATUS_ORDER = ["待派车", "已派车", "作业中", "已完成", "已取消"]
# 动作 → (允许的来源状态, 目标状态)；来源状态不匹配的动作一律拦下
ACTION_RULES = {
    "确认派车": ({"待派车"}, "已派车"),
    "司机接单": ({"已派车"}, "作业中"),
    "确认完单": ({"作业中"}, "已完成"),
    "退回": ({"已派车"}, "待派车"),
    "取消调度": ({"待派车", "已派车"}, "已取消"),
}
NEGATIVE_ACTIONS = ["取消调度"]
# 已派车未完成都算占用，重复派车校验就看这个集合
ACTIVE_STATUSES = {"已派车", "作业中"}
DONE_STATUSES = {"已完成", "已取消"}


class TruckService:
    def _sync(self, row: dict[str, Any]) -> dict[str, Any]:
        """展示字段 调度状态 始终以 status 为准，列表、司机端、接口看到的一致。"""
        row["调度状态"] = str(row.get("status") or STATUS_ORDER[0])
        return row

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
        return [self._sync(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._sync(entry) if entry is not None else None

    def list_driver_jobs(self, driver: str) -> list[dict[str, Any]]:
        """司机端看到的活：按司机姓名取同一份调度数据，状态与调度列表保持一致。"""
        name = driver.strip()
        rows = [row for row in store.rows(MODULE) if str(row.get("司机姓名", "")).strip() == name]
        return [self._sync(row) for row in rows]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        errors = [f"缺少必填字段：{field}" for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        order_no = str(values.get("调度单号") or "").strip()
        if order_no and any(str(row.get("调度单号", "")).strip() == order_no for row in store.rows(MODULE)):
            errors.append(f"调度单号 {order_no} 已存在，不能重复登记")
        if errors:
            return None, errors
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in ENTRY_FIELDS if values.get(field) is not None})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._sync(entry), []

    def run_action(self, entry_id: int, action: str, values: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"集卡 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于集卡调度可执行范围"
        sources, target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current not in sources:
            return None, f"调度单当前为「{current}」，不能执行{action}"
        values = values or {}
        if action == "确认派车":
            error = self._dispatch(entry, values)
            if error:
                return None, error
        if action == "确认完单":
            entry["返回时间"] = str(values.get("返回时间") or date.today().isoformat())
        entry["status"] = target
        entry["pending"] = target not in DONE_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._sync(entry), f"集卡已{action}"

    def _dispatch(self, entry: dict[str, Any], values: dict[str, Any]) -> str | None:
        """派车校验落库：司机、计划装卸时间、派车时间都写回调度单，重复派车在这里拦下。"""
        driver = str(values.get("司机姓名") or entry.get("司机姓名") or "").strip()
        if not driver:
            return "派车前请先填写司机姓名"
        plate = str(entry.get("集卡牌号") or "").strip()
        for row in store.rows(MODULE):
            if row is entry:
                continue
            if str(row.get("集卡牌号", "")).strip() == plate and row.get("status") in ACTIVE_STATUSES:
                return f"集卡 {plate} 在调度单 {row.get('调度单号')} 中已{row.get('status')}，不能重复派车"
        entry["司机姓名"] = driver
        plan_time = str(values.get("计划装卸时间") or entry.get("计划装卸时间") or "").strip()
        if plan_time:
            entry["计划装卸时间"] = plan_time
        entry["派车时间"] = str(values.get("派车时间") or date.today().isoformat())
        return None
