import psutil

def cpu_resources() :
    cpu_percent = psutil.cpu_percent(interval=1)
    per_cpu_usage = psutil.cpu_percent(percpu=True, interval=1)  # 코어별 CPU 사용률
    return [cpu_percent, per_cpu_usage]


def memory_resorces() :
    # total - available) / total * 100
    ram = psutil.virtual_memory()

    # swap with disk
    swap_percent = psutil.swap_memory().percent

    return [ram.percent, swap_percent, ram.available]


def disk_resources() :
    disk_usage = psutil.disk_usage('/').percent
    disk_io = psutil.disk_io_counters()

    return [disk_usage, disk_io[0], disk_io[1], disk_io[2], disk_io[3], disk_io[4]]



import psutil
import time

def get_process_cpu_usage():
    process_list = []
    
    # 첫 번째 호출로 초기화
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 짧은 대기 후 CPU 사용량 확인
    time.sleep(0.1)  # 필요에 따라 조정 가능

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            process_info = proc.info  # 프로세스 정보 가져오기
            if not process_info["cpu_percent"] :
                process_info["cpu_percent"] = 0.0
            process_list.append(process_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    sorted_process_list = sorted(process_list, key=lambda x: x['cpu_percent'], reverse=True)
    return sorted_process_list[:10]


processes = get_process_cpu_usage()

print("{:<10} {:<25} {:<10}".format("PID", "Name", "CPU%"))
print("-" * 50)
for proc in processes:
    print(proc['pid'], proc['name'], proc['cpu_percent'])