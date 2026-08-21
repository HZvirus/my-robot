"""SQLAlchemy ORM models: device users, conversations and messages.

本模块定义了 4 张核心业务表的 ORM 映射：

- users         匿名设备用户（只存设备令牌的 SHA-256 哈希）
- conversations 会话（一次问答对/一轮对话的容器）
- messages      会话中的消息（用户提问或 AI 回复）
- agent_steps   代理单次思考-行动-观察过程（ReAct 循环的足迹）

所有主键均为字符串 UUID（由业务层生成，如 `uuid4().hex`），时间字段
统一使用 `_utcnow` 生成"无时区信息的 UTC 时间"，避免时区混乱。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.rbac import DEFAULT_ROLE
from app.db.session import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间，并去掉 tzinfo（与 SQLite 存储兼容）。

    说明：
    - `datetime.now(UTC)` 得到的是带时区的 aware 时间；
    - `.replace(tzinfo=None)` 转换为 naive 时间，保证写入 SQLite/PostgreSQL
      时不会被时区偏移干扰，读出后统一按 UTC 解释。
    """
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    """匿名设备用户。

    出于隐私考虑，**不保存设备令牌明文**，只保存其 SHA-256 哈希
    （`token_hash` 字段），哈希值不可逆，令牌泄露也不会导致历史数据关联。

    `role` 控制该设备能检索哪些知识库范围（scope），默认为 "patient"
    （普通患者，只能访问 public 范围），角色与范围的映射见
    `app.core.rbac.ROLE_SCOPES`。角色在服务端校验，客户端无法自行提升权限。
    """

    __tablename__ = "users"

    # 用户唯一标识（UUID 字符串，业务层生成）
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 设备令牌的 SHA-256 哈希（64 位十六进制），唯一且建索引，便于按令牌查询用户
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 角色，默认患者（DEFAULT_ROLE），决定可见的知识库范围
    role: Mapped[str] = mapped_column(String(32), default=DEFAULT_ROLE)
    # 用户创建时间（UTC）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Conversation(Base):
    """会话。

    一个会话是一次独立问答的容器，用来把用户与 AI 的多轮消息聚合在一起，
    便于后续按会话查询历史、管理上下文。

    注意：这里刻意**没有外键关联 users 表**，`owner_id` 只是逻辑上的
    用户 ID，且允许为空（匿名/未登录场景），避免与用户表强耦合。
    """

    __tablename__ = "conversations"

    # 会话唯一标识（UUID 字符串）
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 会话归属的用户 ID（逻辑外键，可空；建索引加速按用户查会话）
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 会话创建时的角色快照（可空，用于后续检索该会话知识库范围）
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 会话创建时间（UTC），建索引便于按时间排序/分页
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )


class Message(Base):
    """会话中的单条消息。

    一条消息要么是用户提问（role="user"），要么是 AI 回复（role="assistant"）。
    一条回复可能携带引用的知识库来源（`sources`），也可能被用户中断
    （`interrupted`，用于流式输出被客户端取消时标记半成品回复）。
    """

    __tablename__ = "messages"

    # 消息唯一标识（UUID 字符串）
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 所属会话，外键关联 conversations.id，建索引便于按会话拉取消息列表
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    # 消息角色：user / assistant / system 等
    role: Mapped[str] = mapped_column(String(16))
    # 消息正文（Text 支持长文本）
    content: Mapped[str] = mapped_column(Text)
    # 回答引用的知识库来源列表，如 [{"title": ..., "content": ...}]；JSON 可空
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # 是否被中断（流式输出被取消时置 True，前端可据此显示"回答已中断"）
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    # 消息创建时间（UTC），建索引便于按时间排序/分页
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )


class AgentStep(Base):
    """代理单步执行记录（ReAct 循环足迹）。

    记录一次 agent 迭代中的：

    - thought      模型的思考过程
    - action       采取的动作（如调用哪个工具/查询哪个知识库）
    - observation  动作返回的观察结果

    用于调试、审计和"逐步展示 AI 推理过程"。`step_no` 表示在该会话内的
    步骤序号（从 1 开始）；`status` 记录该步骤的结束状态。
    """

    __tablename__ = "agent_steps"

    # 步骤唯一标识（UUID 字符串）
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 所属会话，外键关联 conversations.id，建索引便于按会话拉取步骤链
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    # 会话内的步骤序号（1, 2, 3 ...）
    step_no: Mapped[int]
    # 思考过程（文本，默认空串）
    thought: Mapped[str] = mapped_column(Text, default="")
    # 采取的动作（文本，默认空串）
    action: Mapped[str] = mapped_column(Text, default="")
    # 动作的观察结果（文本，默认空串）
    observation: Mapped[str] = mapped_column(Text, default="")
    # 步骤状态（如 done / failed / running），默认 "done"
    status: Mapped[str] = mapped_column(String(16), default="done")
    # 步骤创建时间（UTC），建索引便于按时间排序
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
