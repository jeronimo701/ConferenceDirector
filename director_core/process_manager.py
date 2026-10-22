import subprocess

class ProcessManager:
    def __init__(self):
        self.processes = []

    def start(self, args):
        process = subprocess.Popen(args)
        self.processes.append(process)
        return process

    def close_all(self):
        for process in list(self.processes):
            self.close_process(process)

    def close_process(self, process):
        if process and process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, text=True, timeout=5)
        if process in self.processes:
            self.processes.remove(process)


