import asyncio

import pytest

from arclet.letoderea.effect import EffectManager


@pytest.mark.asyncio
async def test_effect_manager():
    manager = EffectManager()

    # 示例 1: 同步清理
    def sync_effect():
        print("Setting up timer")
        timer = asyncio.get_event_loop().call_later(
            1.0, lambda: print("tick")
        )
        def cleanup():
            timer.cancel()
            print("Timer cancelled")
        return cleanup

    dispose1 = manager.effect(sync_effect, "timer")

    # 示例 2: 异步清理
    async def async_effect():
        print("Connecting to database...")
        await asyncio.sleep(0.1)
        resource = "db_connection"
        async def cleanup():
            print(f"Closing {resource}")
            await asyncio.sleep(0.01)
        return cleanup

    dispose2 = manager.effect(async_effect, "database")

    # 示例 3: 多个清理函数（生成器）
    def multi_effect():
        print("Setting up multiple resources...")
        for i in range(3):
            print(f"  Setup resource_{i}")
            yield lambda r=f"resource_{i}": print(f"Cleanup {r}")

    dispose3 = manager.effect(multi_effect, "multiple-resources")

    # 示例 4: 异步生成器
    async def async_gen_effect():
        print("Setting up async resources...")
        for i in range(3):
            await asyncio.sleep(0.01)
            print(f"  Setup async_resource_{i}")
            yield lambda r=f"async_resource_{i}": print(f"Async cleanup {r}")

    dispose4 = manager.effect(async_gen_effect, "async-resources")

    # 获取所有 effect
    effects = manager.get_effects()
    assert [e.label for e in effects] == ["timer", "database", "multiple-resources", "async-resources"]
    assert manager.size == 4

    # 等待一下让异步 effect 启动
    await asyncio.sleep(0.2)

    # 清理所有资源
    print("\nCleaning up all resources...")
    await manager.cleanup()
    print("All cleaned up")

    # 测试单个 dispose
    print("\n--- Testing individual dispose ---")
    dispose5 = manager.effect(sync_effect, "single-timer")
    await asyncio.sleep(0.1)
    print("Disposing single timer...")
    dispose5()
    print("Single timer disposed")


@pytest.mark.asyncio
async def test_nested_effects():
    manager = EffectManager()

    def outer_effect():
        print("Setting up outer effect")

        def inner_effect():
            print("Setting up inner effect")
            return lambda: print("Inner effect cleaned up")
        return manager.effect(inner_effect, "inner")

    manager.effect(outer_effect, "outer")

    effects = manager.get_effects()
    assert len(effects) == 1
    assert effects[0].label == "outer"
    assert effects[0].children and effects[0].children[0].label == "inner"


@pytest.mark.asyncio
async def test_sync_effect_async_cleanup():
    manager = EffectManager()
    executed = []

    def sync_effect():
        executed.append("Setting up sync effect")
        async def cleanup():
            executed.append("Cleaning up sync effect asynchronously")
            await asyncio.sleep(0.1)
        return cleanup

    manager.effect(sync_effect, "sync-with-async-cleanup")

    await asyncio.sleep(0.2)
    print("Cleaning up all resources...")
    await manager.cleanup()
    assert executed == ["Setting up sync effect", "Cleaning up sync effect asynchronously"]
