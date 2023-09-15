# Letoderea
[![Licence](https://img.shields.io/github/license/ArcletProject/Letoderea)](https://github.com/ArcletProject/Letoderea/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/arclet-letoderea)](https://pypi.org/project/arclet-letoderea)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/arclet-letoderea)](https://www.python.org/)

一个高性能，结构简洁，依赖于 Python内置库`asyncio` 的事件系统, 设计灵感来自[`Graia BroadcastControl`](https://github.com/GraiaProject/BroadcastControl)。

项目仍处于开发阶段，部分内容可能会有较大改变

## 安装
### 从 PyPI 安装
``` bash
pip install arclet-letoderea
```

## 样例

```python
from arclet.letoderea import EventSystem, Contexts

es = EventSystem()


class TestEvent:
    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@es.on()
async def test_subscriber(name: str):
    print(name)


es.loop.run_until_complete(es.publish(TestEvent()))
```

## 说明

### 事件

- 事件可以是任何对象，只要实现了 `gather` 异步方法
- `gather` 方法的参数为 `Contexts` 类型，用于传递上下文信息
- 事件可以通过 `gather` 方法将自身想要传递的信息整合进 `Contexts` 中
- 事件系统支持直接查找属性, 例如 `Event.name` 可以直接注入进 `foo(name: str)` 的参数中
- 事件可以携带 `Provider` 与 `Auxiliary`，它们会在事件被订阅时注入到订阅者中

### 订阅

- 通过 `EventSystem.on` 或 `subscribe` 装饰器可以将一个函数注册为事件的订阅者
- 订阅者的参数可以是任何类型，事件系统会尝试从 `Contexts` 中查找对应的值并注入
- 默认情况下 `event` 为名字的参数会被注入为事件的实例
- 订阅者可以设置优先级，值越小优先级越高

### 上下文

- `Contexts` 类型是一个 `dict` 的子类，用于传递上下文信息
- `Contexts` 默认包含 `event` 键，其值为事件的实例
- `Contexts` 默认包含 `$subscriber` 键，其值为订阅者的实例


### 依赖注入

- `Provider[T]` 负责管理参数的注入, 其会尝试从 `Contexts` 中选择需求的参数返回
- 对于订阅者的每个参数，在订阅者注册后，事件系统会遍历该订阅者拥有的所有 `Provider`，
    并依次调用 `Provider.validate` 方法，如果返回 `True`，则将该 `Provider` 绑定到该参数上。
    当进行依赖解析时，事件系统会遍历该参数绑定的所有 `Provider`，并依次调用 `Provider.__call__` 方法，
    如果返回值不为 `None`，则将该返回值注入到该参数中。
- `Provider.validate` 方法用于验证订阅函数的参数是否为该 `Provider` 可绑定的参数。默认实现为检查目标参数的类型声明是否为 `T`。
    也可以通过重写该方法来实现自定义的验证逻辑。
- `Provider.__call__` 方法用于从 `Contexts` 中获取参数
- 原则上 `Provider` 只负责注入单一类型的参数。若想处理多个类型的参数，可以声明自己为 `Provider[Union[A, B, ...]]` 类型，
    并在 `Provider.validate` 方法中进行自定义的逻辑判断。但更推荐的做法是构造多个 `Provider`，并将其绑定到同一个参数上。
- 对于特殊的辅助器 `Depend`，事件系统会将其作为特殊的 `Provider` 处理，绑定了 `Depend` 的参数在解析时将直接调用
    `Depend.__call__` 方法。

### 事件发布

- 一般情况下通过 `EventSystem.publish` 方法可以发布一个事件让事件系统进行处理
- `Publisher` 类负责管理订阅者与事件的交互
- `Publisher.validate` 方法用于验证该事件是否为该发布者的订阅者所关注的事件
- `Publisher.publish` 方法用于将事件不经过事件系统主动分发给订阅者
- `Publisher.supply` 方法用于让事件系统主动获取事件并分发给订阅者
- `EventSystem.on` 与 `EventSystem.publish` 可以指定 `Publisher`，默认为事件系统内的全局 `Publisher`

### 辅助

- `Auxiliary` 提供了一系列辅助方法，方便事件的处理
- `Auxiliary` 分为 `Judge`, `Supply` 与 `Depend` 三类:
    - `Judge`: 用于判断此时是否应该处理事件
    - `Supply`: 用于为 `Contexts` 提供额外的信息
    - `Depend`: 用于依赖注入
- `Auxiliary.scopes` 声明了 `Auxiliary` 的作用域:
    - `prepare`: 表示该 `Auxiliary` 会在依赖注入之前执行
    - `parsing`: 表示该 `Auxiliary` 会在依赖注入解析时执行
    - `complete`: 表示该 `Auxiliary` 会在依赖注入完成后执行
    - `cleanup`: 表示该 `Auxiliary` 会在事件处理完成后执行
- `Auxiliary` 可以设置 `CombineMode`, 用来设置多个 `Auxiliary` 的组合方式:
    - `single`: 表示该 `Auxiliary` 独立执行
    - `and`: 表示该 `Auxiliary` 的执行结果应该与其他 `Auxiliary` 的执行结果都为有效值
    - `or`: 表示该 `Auxiliary` 的执行结果应该与其他 `Auxiliary` 的执行结果至少有一个为有效值

## 开源协议
本实现以 MIT 为开源协议。
