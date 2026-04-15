<div align="center"> 

# Letoderea
[![Licence](https://img.shields.io/github/license/ArcletProject/Letoderea)](https://github.com/ArcletProject/Letoderea/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-letoderea)](https://pypi.org/project/arclet-letoderea)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-letoderea)](https://www.python.org/)
[![codecov](https://codecov.io/gh/ArcletProject/Letoderea/branch/main/graph/badge.svg?token=DOMUPLN5XO)](https://codecov.io/gh/ArcletProject/Letoderea)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/ArcletProject/Letoderea)
[![Docs](https://img.shields.io/badge/docs-arclet.top-28d178)](https://arclet.top/tutorial/letoderea/)
[![QQ 群](https://img.shields.io/badge/QQ-654490750-yellow.svg)](https://jq.qq.com/?_wv=1027&k=PUPOnCSH)

</div>

一个高性能，结构简洁，依赖于 Python内置库`asyncio` 的事件系统, 设计灵感来自[`Graia BroadcastControl`](https://github.com/GraiaProject/BroadcastControl)。

项目仍处于开发阶段，部分内容可能会有较大改变

## 安装
### 从 PyPI 安装
``` bash
pip install arclet-letoderea
```

## 样例

### 基本使用

```python
import asyncio
import arclet.letoderea as le


@le.make_event
class TestEvent:
    name: str


@le.on_global
async def test_subscriber(name: str):
    print(name)


async def main():
    await le.publish(TestEvent("Letoderea"))


asyncio.run(main())
```

### 依赖注入
```python
import asyncio
import arclet.letoderea as le

@le.make_event
class TestEvent:
    name: str

@le.depends()
async def get_msg(event):
    return f"Hello, {event.name}"

@le.on(TestEvent)
async def test_subscriber(msg: str = get_msg):
    print(msg)

async def main():
    await le.publish(TestEvent("Letoderea"))

asyncio.run(main())
```

### 通信
```python
import asyncio
import random
import arclet.letoderea as le

@le.make_event
class Event:
    name: str

@le.make_event(name="rand")
class RandomData:
    seed: int

    def check_result(self, value) -> le.Result[float] | None: ...

@le.on(RandomData)
def random_subscriber(seed: int):
    return random.Random(seed).random()

@le.on(Event)
async def event_subscriber(event: Event):
    print(f"Event: {event.name}")
    result = await le.post(RandomData(42))
    print(f"Random: {result.value}")

async def main():
    await le.publish(Event("Letoderea"))
    
asyncio.run(main())
```

### 过滤
```python
import asyncio
import arclet.letoderea as le


@le.make_event
class Event:
    name: str
    flag: bool = False


@le.on_global
@le.enter_if(le.deref(Event).name == "Letoderea")
async def sub_if_letoderea():
    ...

@le.on(Event).if_(le.deref(Event).flag & (le.deref(Event).name != "Letoderea"))
async def sub_if_not_letoderea():
    ...


async def main():
    await le.publish(Event("Letoderea"))
    await le.publish(Event("OtherEvent", True))

asyncio.run(main())
```


## 说明

### 核心概念

- **事件（Event）**：被发布并分发给订阅者的对象。
- **订阅者（Subscriber）**：注册到事件系统中的函数或协程函数。
- **上下文（Contexts）**：单次分发过程中的共享数据容器（`dict` 子类）。
- **Provider**：参数注入器，在调用订阅者前解析参数。
- **作用域（Scope）**：订阅关系的容器，用于隔离和组织分发流程。

### 事件

- 事件可以是任意对象，满足以下任一条件即可参与分发：
  - 实现 `gather(contexts)` 异步方法；
  - 通过 `define(..., supplier=...)` 提供采集逻辑；
  - 通过 `@gather` 注册 supplier 方法。
- `gather` 用于将事件相关数据写入 `Contexts`。
- 事件可携带 `Provider`，用于为订阅者参数提供注入能力。
- 订阅子类事件时，父类事件的 `Provider` 会被继承。
- 订阅父类事件时，子类事件同样会被分发给该订阅者。

### 注册方式

- **装饰器流派**：通过 `on`、`use`、`on_global` 将函数注册为订阅者。
- **显式调用流派**：通过 `Scope.register` 完成注册。
- 上述方式都会返回 `Subscriber`，可通过 `.dispose()` 取消订阅。
- 订阅者支持优先级，值越小优先级越高。

### 订阅与参数注入

- 订阅者参数可为任意类型，系统会尝试从 `Contexts` 查找并注入。
- 默认情况下，参数名为 `event` 时会注入当前事件实例。
- `Provider[T]` 负责管理参数注入流程。
- 在注册阶段，系统会为每个参数遍历可用 `Provider`，调用 `Provider.validate` 判断是否可绑定。
- 在执行阶段，系统按绑定顺序调用 `Provider.__call__`；当返回值不为 `None` 时完成注入。
- `Depend` 会被作为特殊 `Provider` 处理：参数解析时直接调用其绑定方法。
- `Provider` 支持优先级（值越小越高）。

### 上下文

- `Contexts` 是 `dict` 子类，用于在分发链路中共享数据。
- 默认包含 `$event`（当前事件实例）与 `$subscriber`（当前订阅者实例）。
- 订阅者执行后，返回值写入 `$result`。
- 参数解析异常会写入 `$error`，用于后续处理与调试。

### 事件发布

- `publish(event)`：分发给所有匹配订阅者。
- `post(event)`：当某个订阅者返回有效值后立即停止，并返回该值。
- `waterfall(event)`：按匹配顺序串行执行订阅者，并将上一个订阅者的结果作为后续处理可用输入逐步传递。
- `Publisher.validate` 用于判断事件是否由该发布者处理。
- `Publisher.supply` 用于让系统主动产出事件并完成分发。
- `use` 与 `Scope.register` 可指定 `Publisher`。
- 可通过 `define` 定义发布者，并在 `.use` 等位置按名称引用。

### 作用域

- `Scope` 负责管理订阅者与事件的匹配和分发关系。
- 所有订阅者都存储在某个 `Scope` 中。
- `publish` 与 `post` 可指定目标 `Scope`。

### 传播

- `Subscriber.propagate` 用于注册同级传播订阅者。
- `prepend=True` 时前置执行，否则在当前订阅者后执行。
- 后置传播订阅者可获取上一个订阅者的返回值。
- 传播订阅者会继承当前订阅者的 `Provider`。
- 返回 `STOP` 可中止同级传播。
- 若传播订阅者依赖暂未满足，系统会尝试延迟执行；若最终都无法满足，会抛出异常。
- `propagate` 支持优先级，也可接收 `Propagator` 通过 `compose` 批量提供传播订阅者。

### 异常处理与错误传播

- 订阅者执行期间发生异常时，系统会在当前 `Contexts` 中记录 `$error`。
- 依赖解析失败且无法通过延迟满足时，会抛出异常而非静默忽略。
- 异常可在同一分发链路中被后续逻辑感知并处理，便于统一收敛错误。

### 条件过滤与匹配细节

- 可通过 `if_`、`enter_if` 为订阅者增加条件过滤。
- 条件表达式可基于事件字段、上下文值与组合逻辑进行匹配。
- 事件匹配除类型外，还支持更细粒度的命名或模式匹配场景，用于减少无效分发。

### 作用域隔离与链路控制

- 不同 `Scope` 之间的订阅关系彼此隔离，适合模块化与测试隔离场景。
- 可在指定 `Scope` 内调用 `publish`、`post`、`waterfall`，实现独立分发。
- 通过传播链（前置/后置）与 `STOP` 可实现链路短路和流程控制。
