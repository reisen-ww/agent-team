# 最小记录模板

选用缺少的字段，合并进已有项目记录；不要机械复制成多套文件。下列记录不是可执行调度配置，未知值不能自动当作获准。

## 运行约定

```yaml
run_id: example-run
task_kind: coding
mode: small-team
requirements: {location: project-defined, revision: R1}
authorization: {source: human-confirmation, scope: this-run}
user_interface_owner: current-chat
roles: {}  # 记录实际人员/会话及角色合并、模型选择；不填虚构ID
shared_records: project-defined
capacity: {max_members: null, max_active_requests: null}
budget: {unit: null, limit: null, counter_owner: null, enforcement: soft}
rework: {global_batch_limit: null, per_worker_limit: null, counter_owner: null}
review_mode: supervisor-plus-agreed-verification
integration: {executor: null, acceptance_owner: null}
notifications: exceptions-only
resume_owner: user-interface-owner
```

null 表示尚未约定，不是无限资源或已获授权。是否需要该字段按任务判断；影响派工的关键值未明确时不派相应工作。没有 Team 就无需填写成员/并发字段。

## 工作包

```text
任务ID / 原需求版本 / 结果负责人 / 实施拥有者
目标与完成条件
输入、接口、依赖和已知假设
允许读写范围、独占资源和禁止事项
可自行决定 / 需升级的事项
验证方式、交付位置、预算和停止条件
问题交给谁；谁执行集成与验收
```

## 交付/验收卡

```text
任务/需求版本；产物路径及提交/指纹
测试作者、执行者、验收者与各自覆盖范围
实际命令/方法、环境、原始日志、结果
首次失败和必要修复；引用全局返工batch_id
已满足、未满足、未知和待用户反馈项
当前状态、下一推进人和恢复条件
```

## 通知

```text
任务/版本：发生的变化；对接收人的影响；证据位置；需要的具体动作。
```

不需要动作的普通收悉不回复；正文已有文件时只传定位和差异。报告只保留与决定有关的内容，原始证据保留可追溯入口。
