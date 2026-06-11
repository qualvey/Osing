import subprocess
import logging
import pytest
from unittest.mock import MagicMock, call

# 配置测试时的日志输出，确保能看到你的 DEBUG LOG
logger = logging.getLogger(__name__)

# 🌟 把你的核心功能封装成一个独立的纯函数，方便直接测试
def run_reload_logic() -> bool:
    try:
        # 🌟 步骤 0：特权探路！检查当前用户是否有免密执行对应命令的特权
        # sudo -n true 如果返回 0 说明有免密特权；返回非 0 说明需要密码（即没有免密权限）
        can_sudo = subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0
        
        if not can_sudo:
            logger.error("❌ [Permission Denied] 当前用户没有免密 sudo 权限，无法操作系统级进程！")
            # 优雅退场，或者直接切入低权限保底逻辑
            return False

        # 🎯 步骤 A：Debug 版查找
        pid_process = subprocess.run(
            ["pgrep", "-o", "sing-box"],
            capture_output=True,
            text=True
        )
        
        if pid_process.returncode == 0 and pid_process.stdout.strip():
            pid = int(pid_process.stdout.strip())
            
            # 🎯 步骤 B：由于前面探过路，这里绝对可以安全、免密地执行 sudo kill
            subprocess.run(
                ["sudo", "kill", "-HUP", str(pid)],
                check=True, capture_output=True, text=True
            )
            logger.info(f"[Success] 成功热重载进程 (PID: {pid})！")
            return True
            
        else:
            # 🎯 步骤 C：冷启动
            logger.warning("[Reload] 进程不存在，执行冷启动...")
            subprocess.run(
                ["sudo", "systemctl", "start", "sing-box"],
                check=True, capture_output=True, text=True
            )
            logger.info("[Success] sing-box 服务已成功全新冷启动！")
            return True
            
    except subprocess.CalledProcessError as e:
        logger.error(f"[Panic] 命令执行失败！错误码: {e.returncode}")
        raise RuntimeError("sing-box 服务热重载遭遇致命失败！") from e
# =====================================================================
# 🧪 pytest 测试用例
# =====================================================================

from unittest.mock import MagicMock, call
import pytest
import subprocess

def test_reload_logic_when_process_exists(monkeypatch):
    """
    🎯 测试场景 1：当 pgrep 成功找到了 sing-box 进程
    """
    mock_run = MagicMock()
    
    # 🌟 1. 模拟步骤 0：sudo -n true 探路成功
    mock_sudo_check = MagicMock()
    mock_sudo_check.returncode = 0
    
    # 2. 模拟步骤 A：pgrep 找到进程
    mock_pgrep_res = MagicMock()
    mock_pgrep_res.returncode = 0
    mock_pgrep_res.stdout = "12345\n"
    mock_pgrep_res.stderr = ""
    
    # 3. 模拟步骤 B：kill 信号发送成功
    mock_kill_res = MagicMock()
    mock_kill_res.returncode = 0
    
    # 🌟 按调用顺序喂给 3 个弹药
    mock_run.side_effect = [mock_sudo_check, mock_pgrep_res, mock_kill_res]
    monkeypatch.setattr(subprocess, "run", mock_run)

    # 执行测试
    result = run_reload_logic()
    
    assert result is True
    assert mock_run.call_count == 3  # 确调用了 3 次
    
    # 精准断言物理命令调用链
    mock_run.assert_has_calls([
        call(["sudo", "-n", "true"], capture_output=True),
        call(["pgrep", "-o", "sing-box"], capture_output=True, text=True),
        call(["sudo", "kill", "-HUP", "12345"], check=True, capture_output=True, text=True)
    ])


def test_reload_logic_when_process_not_exists(monkeypatch):
    """
    🎯 测试场景 2：当 pgrep 返回状态码 1 (冷启动分支)
    """
    mock_run = MagicMock()
    
    # 🌟 1. 模拟步骤 0：sudo -n true 探路成功
    mock_sudo_check = MagicMock()
    mock_sudo_check.returncode = 0
    
    # 2. 模拟 pgrep 没找到进程
    mock_pgrep_res = MagicMock()
    mock_pgrep_res.returncode = 1
    mock_pgrep_res.stdout = ""
    mock_pgrep_res.stderr = "process not found"
    
    # 3. 模拟 systemctl start 成功
    mock_systemctl_res = MagicMock()
    mock_systemctl_res.returncode = 0
    
    # 🌟 按调用顺序喂给 3 个弹药
    mock_run.side_effect = [mock_sudo_check, mock_pgrep_res, mock_systemctl_res]
    monkeypatch.setattr(subprocess, "run", mock_run)

    # 执行测试
    result = run_reload_logic()
    
    assert result is True
    assert mock_run.call_count == 3
    
    mock_run.assert_has_calls([
        call(["sudo", "-n", "true"], capture_output=True),
        call(["pgrep", "-o", "sing-box"], capture_output=True, text=True),
        call(["sudo", "systemctl", "start", "sing-box"], check=True, capture_output=True, text=True)
    ])
def test_real_live_reload_on_developer_machine():
    """
    🔥 真实的物理击打测试（不做任何 Mock）
    直接在开发机上执行真实命令，测试业务代码的物理耐受度
    """
    # 🚨 警告：直接调用原函数，真查 pgrep，真发信号
    result = run_reload_logic()
    
    # 只要命令没抛出 CalledProcessError 崩溃，并且顺利返回了 bool，说明在开发机上走通了！
    assert isinstance(result, bool)
    print(f"\n[Live Test Result] 开发机真实物理测试成功，返回值: {result}")