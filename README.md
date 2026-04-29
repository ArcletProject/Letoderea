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

Letoderea 围绕 **事件 → 发布 → 订阅** 的模型构建，提供依赖注入、条件过滤、作用域隔离等能力，适用于需要灵活解耦的异步应用场景。

### 核心概念

| 概念             | 说明                        |
|----------------|---------------------------|
| **Event**      | 被发布并分发给订阅者的对象             |
| **Subscriber** | 注册到事件系统中的函数或协程函数          |
| **Contexts**   | 单次分发过程中的共享数据容器（`dict` 子类） |
| **Provider**   | 参数注入器，在调用订阅者前解析并注入参数      |
| **Scope**      | 订阅关系的容器，用于隔离和组织分发流程       |
| **Publisher**  | 事件类型的注册与验证单元，管理事件的匹配和供给   |

### 事件

事件可以是任意对象，满足以下任一条件即可参与分发：

- 实现 `gather(contexts)` 异步方法
- 通过 `define(..., supplier=...)` 提供采集逻辑
- 通过 `@gather` 注册 supplier 方法

`gather` 负责将事件携带的数据写入 `Contexts`，供后续订阅者消费。

事件支持继承语义：
- 事件可携带 `Provider`，子类事件会继承父类的 `Provider`
- 订阅父类事件时，子类事件同样会被分发给该订阅者

### 注册与订阅

提供两种注册方式：

```
装饰器：on / use / on_global → 将函数直接注册为订阅者
显式调用：Scope.register       → 手动注册到指定作用域
```

两种方式均返回 `Subscriber` 实例，可通过 `.dispose()` 取消订阅。订阅者支持优先级（值越小优先级越高，默认 16）。

### 依赖注入

订阅者的参数由 `Provider` 体系自动解析和注入：

1. **注册阶段**：系统遍历可用 `Provider`，调用 `validate` 判断每个参数的绑定关系
2. **执行阶段**：按绑定顺序调用 `Provider.__call__`，返回值非 `None` 时完成注入

内置规则：
- 参数名为 `event` 时自动注入当前事件实例
- `depends()` 装饰的函数会被作为特殊 `Provider`，在参数解析时直接调用
- `Provider` 支持优先级（值越小越高）

### 上下文

`Contexts` 在分发链路中共享数据，内置以下键：

| 键             | 含义             |
|---------------|----------------|
| `$event`      | 当前事件实例         |
| `$subscriber` | 当前订阅者实例        |
| `$result`     | 订阅者执行后的返回值     |
| `$error`      | 参数解析或执行期间的异常信息 |

### 事件发布

三种发布策略适用于不同场景：

| 方法                 | 行为                                  |
|--------------------|-------------------------------------|
| `publish(event)`   | **广播** — 分发给所有匹配订阅者（按优先级分组并发）       |
| `post(event)`      | **请求-响应** — 首个有效返回值即刻停止，返回 `Result` |
| `waterfall(event)` | **瀑布流** — 串行执行，上一个结果作为后续可用输入逐步传递    |

此外：
- `Publisher.validate` 用于判断事件是否由该发布者处理
- `Publisher.supply` 用于主动产出事件并完成分发
- 可通过 `define` 定义发布者，并在 `use` 等位置按名称引用

### 条件过滤

通过 `if_` / `enter_if` / `bypass_if` 为订阅者增加前置条件：

```python
# 装饰器风格
@enter_if(deref(Event).name == "target")

# 链式风格
@on(Event).if_(deref(Event).flag & (deref(Event).name != "other"))
```

条件表达式支持基于事件字段的比较、布尔组合等操作。

### 传播

`Subscriber.propagate` 用于注册同级传播处理器，构建订阅者的前置/后置执行链：

- `prepend=True` 时前置执行，否则后置
- 后置传播处理器可获取上一个订阅者的返回值（`$result`）
- 传播处理器继承当前订阅者的 `Provider`
- 返回 `STOP` 可中止传播链
- 支持 `Propagator` 通过 `compose` 批量提供传播处理器

### 作用域隔离

`Scope` 在模块化与测试场景中提供订阅关系的隔离：

- 不同 `Scope` 之间的订阅关系彼此独立
- `publish` / `post` / `waterfall` 均可指定目标 `Scope`
- 通过传播链与 `STOP` 可实现链路短路和流程控制
