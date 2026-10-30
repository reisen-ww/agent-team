# 可选的离线运行记录

需要复现示例或检查跨任务记录时使用。已有任务系统可保留自己的格式，只需表达等价信息；本格式不是所有团队的必填配置，也不创建授权。

`scripts/check_run.py` 使用 Python 3.10+ 标准库，只读一个 JSON 文件并输出 JSON 检查结果；通过返回 0，发现问题或无法解析返回 1。它只验证下面的记录一致性，不调用模型、工具或网络，不执行记录内的命令，不读取记录所指的证据正文，不修改输入文件。手工伪造的健康记录仍可通过，因而不能证明真实执行、身份、预算或权限已受约束。

## 字段约定

根对象包含 `schema_version: 1`、非空 `run_id`、`protocol_version`、`evidence_level`，以及 `requirements`、`tasks`、`actions`、`deliveries`、`executions`。`evidence_level` 取 `illustrative` 或 `recorded`；后者只是记录声明，并非验证器授予的可信等级。

- `requirements`：需求 ID 到当前有效版本的字典，例如 `REQ-total: R2`。
- `tasks`：任务数组。每项含唯一 `id`、非空 `owner`、`status`、`artifact_revision`、`requirements`、`inputs`、`waiting_on` 和 `acceptance`。
  - `status` 为 `ready`、`in_progress`、`blocked`、`review_required`、`accepted` 或 `cancelled`。未产出时 `artifact_revision` 可为 null。
  - `requirements` 是该任务采用的需求 ID/版本；`inputs` 是直接输入任务 ID/产物版本；`waiting_on` 是尚待决定或交付的任务 ID 数组。依赖必须存在且不能指向自己。
  - 尚未验收时 `acceptance` 为 null；否则为包含 `artifact_revision`、`requirements`、`inputs`、非空 `reviewer` 和非空 `evidence` 数组的快照。证据条目为定位字符串，不代表工具核读过它。
  - `accepted` 必须有产物和验收快照。快照与当前任务产物、采用的需求/输入完全相符；需求版本匹配根对象，输入任务已验收且产物版本匹配；不能仍有等待项。上游尚待复核时，下游不能继续标已验收。
  - 未验收的任务可保留旧版本以表达待复核现场；不能通过删去实际需求/依赖来制造通过。检查器不知道真实工作是否遗漏了依赖，负责人仍须核查完整性。
- `actions`：本次记录涉及的逻辑执行动作账本。每项含唯一 `id`、存在的 `task_id`、非空 `input_version`、JSON 对象 `payload`、`state`、`result_ref`。状态取 `pending`、`in_progress`、`completed`、`unknown`、`failed`、`not_executed`、`cancelled`；只有 `completed` 必须有非空结果定位。任务标为 accepted 时，其动作不能尚处于 pending、in_progress 或 unknown。
- `deliveries`：投递记录，含唯一 `id`、`action_id`、`task_id`、`input_version`、`payload`。允许多次投递同一动作，但任务、输入版本和负载必须与账本完全一致；同编号改内容是冲突。比较 JSON 值，不依赖对象键顺序。
- `executions`：开始执行的记录，含唯一 `id` 和 `action_id`；同动作最多一项。重投次数与执行次数分开记录。这里的次数是记录值，不是真实工具计费计数。

这里的 `deliveries` 仅指执行动作的投递记录，不表示某个成果已交付或验收。普通知会、事实核对与意见不必全部登记为 actions/deliveries；消息用途与接收规则见 [记录与通信](coordination.md#消息与插队)。结构检查不验证消息标签、身份或授权是否真实，也不验证接收者已经理解。

明确需要再次尝试时，先确认原动作 `failed` 或 `not_executed`，新动作使用新 ID 并带 `retry_of` 指向原动作及非空 `retry_decision_ref`。后续尝试沿用同一任务、需求和累计预算；这两个字段只定位有权者的决定，不授予权限。原动作 unknown/in_progress 不允许用新 ID 重试。重试链不能循环，同一前序动作最多有一个直接重试后继，避免分叉重复执行；进一步尝试链接到最近一次已确定失败的动作。

检查器拒绝重复 ID、缺失引用、动作冲突、重复执行、无结果的 completed、未对账重试、输入依赖环和 waiting_on 等待环。它不自动选择修复、改状态、重新派工或恢复冻结。无动作的示例允许三个动作数组为空。

failed 表示已核清失败结果及副作用，不是把任意报错转成可重试。若存在部分成功而无法确定影响，仍保留 unknown。该语义由真实对账证据支持，检查器只能检查记录中声明的状态。

## 指标

可选 `metrics` 对象：`accepted_deliverables`（非负整数）、`elapsed_minutes`、`review_wait_minutes`、`integration_wait_minutes`、`rework_batches`（非负整数）和 `billed_cost`。时间可为 null 或非负有限数；布尔值不作为数值。`billed_cost` 为 null，或包含非负有限 `amount`、非空 `currency`、`source`、`read_at` 的对象。缺账单就填 null，不能以模型标价估算冒充实付；汇总口径须由负责人在记录外说明。

验收数应等于 tasks 中 accepted 的数量；分开报告任务级交付与项目级成果，不能把拆细任务当作产能提升。等待时间可能重叠，不直接相加充当墙钟。字段可以缺省，检查器不替你采集或推算。

参见 [小团队样例](../examples/small-team/README.md)。
