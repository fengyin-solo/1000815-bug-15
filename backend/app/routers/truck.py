"""集卡调度接口：覆盖登记、派车、接单、完单、退回与司机端任务查询。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.truck import TruckService

router = APIRouter(prefix="/api/truck", tags=["集卡调度"])

service = TruckService()

LIST_FIELDS = ["调度单号", "集卡牌号", "司机姓名", "作业任务", "计划装卸时间", "派车时间", "返回时间", "所属车队", "调度状态"]
STATUSES = ["待派车", "已派车", "作业中", "已完成", "已取消"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按调度单号检索"),
    status: str | None = Query(default=None, description="待派车、已派车、作业中、已完成、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按调度单号与状态过滤集卡调度列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出集卡调度清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "truck", "total": total, "items": items}


@router.get("/driver/tasks", response_model=PageResult[dict])
def driver_tasks(driver: str = Query(..., description="司机姓名")) -> PageResult[dict]:
    """司机端任务列表：司机只看派给自己的单子，状态与调度列表同源。"""
    name = driver.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请先填写司机姓名再查询任务")
    items = service.driver_tasks(name)
    return PageResult(items=items, total=len(items), page=1, size=len(items) or 1)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条集卡明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"集卡调度单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条调度单；缺字段或调度单号重复时说明原因而不是静默丢弃。"""
    entry, message = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条调度单执行派车、接单、完单、退回、取消调度；越权或重复派车会被拦下并说明原因。"""
    values = dict(payload.values)
    action = str(values.pop("action", "") or "").strip()
    entry, message = service.run_action(entry_id, action, values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
