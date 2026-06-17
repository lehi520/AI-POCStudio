"""
后台进程异步沙箱执行器
负责在隔离环境中运行 AI 生成的 POC 脚本，实时捕获输出
"""

import os
import sys
import uuid
import subprocess
import threading
import tempfile
from typing import Callable, Optional


class SandboxExecutor:
    """轻量级本地沙箱执行器"""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._temp_dir = tempfile.mkdtemp(prefix="ai_poc_sandbox_")

    def run_script(self, code: str, args: list = None,
                   on_stdout: Callable[[str], None] = None,
                   on_stderr: Callable[[str], None] = None,
                   on_finish: Callable[[int, str], None] = None):
        """
        异步执行 Python 脚本

        Args:
            code: Python 代码字符串
            args: 命令行参数列表（如 ["--target", "http://xxx"]）
            on_stdout: stdout 每行输出的回调
            on_stderr: stderr 每行输出的回调
            on_finish: 执行结束的回调（退出码, 完整 stderr 内容）
        """
        # 停止上一次运行
        self.stop()

        # 写入临时文件
        script_id = uuid.uuid4().hex[:8]
        script_path = os.path.join(self._temp_dir, f"poc_{script_id}.py")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(code)

        # 构建命令
        cmd = [sys.executable, "-u", script_path]  # -u 禁用缓冲，确保实时输出
        if args:
            cmd.extend(args)

        self._stop_event.clear()

        def _execute():
            stderr_output = []
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,  # 行缓冲
                    cwd=self._temp_dir,
                    # 创建新的进程组，方便后续终止
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )

                # 实时读取 stdout
                def _read_stdout():
                    try:
                        for line in iter(self._process.stdout.readline, ''):
                            if self._stop_event.is_set():
                                break
                            if on_stdout:
                                on_stdout(line.rstrip('\n'))
                    except Exception:
                        pass

                # 实时读取 stderr
                def _read_stderr():
                    try:
                        for line in iter(self._process.stderr.readline, ''):
                            if self._stop_event.is_set():
                                break
                            stderr_output.append(line)
                            if on_stderr:
                                on_stderr(line.rstrip('\n'))
                    except Exception:
                        pass

                t_out = threading.Thread(target=_read_stdout, daemon=True)
                t_err = threading.Thread(target=_read_stderr, daemon=True)
                t_out.start()
                t_err.start()

                # 等待进程结束
                self._process.wait()
                t_out.join(timeout=2)
                t_err.join(timeout=2)

                exit_code = self._process.returncode
                full_stderr = ''.join(stderr_output)

                if on_finish:
                    on_finish(exit_code, full_stderr)

            except Exception as e:
                if on_finish:
                    on_finish(-1, f"[沙箱执行异常] {e}")
            finally:
                # 清理临时文件
                try:
                    os.remove(script_path)
                except OSError:
                    pass

        self._thread = threading.Thread(target=_execute, daemon=True)
        self._thread.start()

    def stop(self):
        """终止当前运行的进程"""
        self._stop_event.set()
        if self._process and self._process.poll() is None:
            try:
                # Windows: 使用 taskkill 强制终止进程树
                if os.name == 'nt':
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self._process.pid)],
                        capture_output=True, timeout=5
                    )
                else:
                    os.killpg(os.getpgid(self._process.pid), 9)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None

    def is_running(self) -> bool:
        """检查是否有脚本正在运行"""
        return self._process is not None and self._process.poll() is None

    def cleanup(self):
        """清理临时目录"""
        self.stop()
        try:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass
