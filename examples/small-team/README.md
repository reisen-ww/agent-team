# 一个主管、两个执行者：订单汇总

这是可复用的演练包，不含真实人员、会话 ID、授权或付费记录。`records/` 全部标记 illustrative；其中的完成状态、产物版本和证据定位是教学数据，不能作为任何模型能力、用户验收或生产可靠性的证据。

## 1. 两种用法

**离线记录演练**不调用模型。从 Skill 根目录执行下面的正反例，检查器只读取 JSON：

```sh
python -B scripts/check_run.py examples/small-team/records/01-accepted-r1.json
python -B scripts/check_run.py examples/small-team/records/02-impact-pending.json
python -B scripts/check_run.py examples/small-team/records/03-accepted-r2.json
python -B scripts/check_run.py examples/small-team/records/04-stale-acceptance.invalid.json
python -B scripts/check_run.py examples/small-team/records/05-duplicate-execution.invalid.json
python -B scripts/check_run.py examples/small-team/records/06-unknown-retry.invalid.json
python -B scripts/check_run.py examples/small-team/records/07-wait-cycle.invalid.json
```

前三个返回 0，后四个返回 1。第 02 例并未完成，返回 0 只表示它如实记录待复核，没有冒称通过。

**真实团队演练**由使用者在新的获准目录执行。先确认实际工具、成员形态、模型、并发/预算、通知、停止和验收人，再创建或复用成员。下文的角色表、提示词和模拟 PM 决定均不是现实授权。工具不支持独立聊天时，不能声称已完成独立聊天实验；按宿主要求选择已授权原生子代理或报告缺口。

## 2. 明确这一轮

任务：做一个 Python 3.10+ 命令行订单汇总程序，无第三方依赖。输出一行 JSON：`total_cents` 为整数，金额只用整数分。输入允许的状态为 `paid`、`cancelled`；金额非负整数，布尔值不是金额。缺字段、非法状态、负数、非整数、损坏 JSON 或错误根类型应非零退出，不能输出成功汇总。

- **R1**：汇总所有订单，包括已取消订单。给定 `fixtures/orders.json`，期望 2300；空数组为 0。
- **R2**：默认排除已取消订单，期望 1800；加 `--include-cancelled` 时仍为 2300。R2 是一次演练中的用户变更，需真实使用者确认后才生效。
- 输出程序：`product/total.py` 提供 `total_cents(orders, include_cancelled=True)`；R2 不改这个明确传参的函数默认值，CLI 负责新版默认行为。`product/cli.py INPUT [--include-cancelled]` 负责解析/打印。这样接口可以先定，两个包在 R1 可并行。
- 文件与权限：全体只读本演练说明和 fixtures。执行者 A 只写 `product/total.py`、`tests/test_total.py`；B 只写 `product/cli.py`、`tests/test_cli.py`；主管只写 `work/`，负责集成执行、证据与验收。需要改变归属时先记录移交，不借集成随手改他人文件。
- 模型使用角色名即可；不要求固定型号。主管兼技术经理对接真实用户，执行者问题交主管。默认自查、自测、主管审查和组合验收，不创建员工审查树。
- 成员/请求额度、累计预算和允许的返工额度由使用者确定。本例两个执行者是演练拓扑，不自动批准两次调用。主管在约定额度内派发，达到上限保存缺口，不重置记录继续。

创建新的演练目录，将本目录的 `fixtures/` 和 `accept.py` 复制进去（无需复制虚构结果）。记录真实允许范围的绝对路径。工作包各自包含本说明、固定输入、已有契约、验收方法、停止条件、交付与问题路由；首次交接直接执行，不先空报到。

## 3. 两份首次工作包

**A / CALC**：实现固定函数和输入校验；只写 A 的两个文件。R1 汇总全部订单。兼容约定参数以便 R2 通过传参排除 cancelled。自测正常、空集和错误输入；交真实命令、原始输出、文件指纹、未覆盖项及本任务采用的需求/接口版本。

**B / CLI**：根据固定契约实现参数解析和 JSON 输出；只写 B 的两个文件。R1 调用函数包含 cancelled，保留显式 `--include-cancelled` 参数。可先用测试替身验证参数解析，不能据此宣布整体集成通过；CALC 产物就绪后使用真实模块验证。CLI 交付引用 CALC 的实际版本，问题交主管。

**主管**：核实输入、写入范围与总额度；接收自测后亲读实现/原始证据，检查 R1，执行组合验收。若有修复，归并到有边界的全局返工批次并交原拥有者，不重置次数。将证据存入 work/，记录三方身份：测试作者、实际执行者、验收者。验收脚本由示例包提供，不可把它称为独立代理审查。

```sh
python -B -m unittest discover -s tests -v
python -B accept.py --revision R1 --program product/cli.py
```

`accept.py` 会使用当前 Python 执行指定程序，输入只含合成订单；必须在允许执行该程序的演练目录中使用。它不安装依赖、不联网，测试输入在临时目录中自动清理。所有结果仍需实际保存；本包不预填模型交付日志。

## 4. 插入一次变更

真实用户确认 R2 后，主管记录变更来源与有效需求版本。CALC 对应计算规则需要重新核验，CLI 依赖 CALC，因此两项原验收暂标待复核，其他无关工作继续。若函数本已支持显式排除，A 可证明无需改代码；B 更新 CLI 默认值及回归。

不要机械增加版本标签使记录变绿。A 提交与 R2 对应的验证及判断；B 引用实际获准的 CALC 版本。主管复核影响并执行：

```sh
python -B accept.py --revision R2 --program product/cli.py
```

固定整体产物及验收证据。历史 R1 结论保留，不能用它替代 R2。`02-impact-pending.json` 示范影响阶段，`03-accepted-r2.json` 示范闭环；版本名以真实代码/输入指纹或提交为准。

## 5. 重投、断连与暂停

同一修复通知可投递两次，但沿用同一个动作编号，例如 `run-demo/fix-cli-r2`。接收者先读动作账本；完成则引用已有结果，执行中不重派，unknown 先对账。第 03 例展示两次投递、一次执行；第 05 例展示不应被接受的两次执行。

模拟断连时，用合成记录表达 unknown，不故意切断真实服务或制造外部副作用。第 06 例故意在 unknown 未查清时使用新 ID 重试，检查应失败。只有能确认原结果并且已有授权允许再次尝试时，才记录 `retry_of` 和决定；累计费用/返工照常。

真实用户暂停时，主管停新增派发并核实在途状态，保存每个成员的产物、动作状态、未完承诺和恢复条件。无法确认已停就记录未知，不能接管仍可能被写入的文件。演练恢复须由有权者明确范围和版本；读取共同记录，排除旧拥有者和旧消息后接续。仅在一段文字中写“暂停成功”不算实测。检查器不验证实际暂停或取消过程。

## 6. 验收与衡量

完成标准是 R2 真实产物、主管审查、正反输入与整体运行均有证据，既定额度内的必须项完成。执行者自测、组合测试和用户反馈分别报告。费用没有账单则为 null；记录任务级合格交付数、端到端耗时、待审与集成等待、返工批次，不从虚构记录推导人数优劣。

共享记录可使用已有系统，或按 [可选记录格式](../../references/run-record.md) 填写。对真实运行使用 `evidence_level: recorded`，并保留可核查的实际证据；这个标签本身并不赋予可信性。只有真实运行过的步骤可以写实测通过。
