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


@es.on(TestEvent)
async def test_subscriber(name: str):
    print(name)


es.loop.run_until_complete(es.publish(TestEvent()))
```

## 特性

### 事件

- 事件可以是任何对象，只要实现了 `gather` 异步方法
- `gather` 方法的参数为 `Contexts` 类型，用于传递上下文信息
- 事件可以通过 `gather` 方法将自身想要传递的信息整合进 `Contexts` 中
- 事件系统支持直接查找属性, 例如 `Event.name` 可以直接注入进 `foo(name: str)` 的参数中
- 事件可以携带 `Provider` 与 `Auxiliary`，它们会在事件被订阅时注入到订阅者中

### 订阅

- 通过 `EventSystem.on` 或 `subscribe` 装饰器可以将一个函数注册为事件的订阅者
- 订阅者的参数可以是任何类型，事件系统会尝试从 `Contexts` 中查找对应的值并注入
- 订阅者的参数可以是 `Contexts` 类型，用于获取事件的上下文信息
- 默认情况下 `event` 为名字的参数会被注入为事件的实例

### 上下文

- `Contexts` 类型是一个 `dict` 的子类，用于传递上下文信息
- `Contexts` 默认包含 `event` 键，其值为事件的实例
- `Contexts` 默认包含 `$subscriber` 键，其值为订阅者的实例

### 发布

- 通过 `EventSystem.publish` 方法可以发布一个事件
- `Publisher` 负责管理订阅者与事件的交互
- `Publisher.validate` 方法用于验证该事件是否为该发布者的订阅者所关注的事件
- `Publisher.publish` 方法用于将事件主动分发给订阅者
- `Publisher.supply` 方法用于给事件系统提供可能的事件
- `EventSystem.on` 与 `EventSystem.publish` 可以指定 `Publisher`，默认为事件系统内的全局 `Publisher`

### 参数

- `Provider[T]` 负责管理参数的注入, 其会尝试从 `Contexts` 中选择需求的参数返回
- `Provider.validate` 方法用于验证订阅函数的参数是否为该 `Provider` 所关注的参数
- `Provider.__call__` 方法用于从 `Contexts` 中获取参数

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
