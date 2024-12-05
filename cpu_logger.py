#!/usr/bin/env python

import platform
import datetime
import psutil
import subprocess
import sys
import time
import contextlib
from resources.cpu import cpu_resources, memory_resorces, disk_resources, get_process_cpu_usage
import boto3
import uuid

# 파일을 닫을 수 있도록 하는 Contextlib 라이브러리 사용, contextmanager 데코레이터를 사용
@contextlib.contextmanager
def smart_open(filename=None, mode='a'):
    if filename:
        hf = open(filename, mode)
    else:
        hf = sys.stdout
    try:
        yield hf
    finally:
        if hf is not sys.stdout:
            hf.close()





# Logger 클래스가 실행되면 argparser를 통해 받은 인자를 반영하여 클래스를 생성한다. 
# 인자가 설정되어 있지 않으면 아래의 값에서 설정한 default로 설정
class Logger():
    def __init__(
            self,
            fname=None, style=None, date_format=None,
            refresh_interval=20, iter_limit=2,
            show_header=False, header_only_once=True,
            threshold_for_target=20,  watch_target="CPU",
            show_units=True, sep=',',
            ):
        
        self.fname = fname if fname else None
        self.style = style or ('tabular' if fname is None else 'csv')
        # dataformat csv
        self.date_format = date_format
        # cpu 및 memory 사용량 수집 주기
        self.refresh_interval = refresh_interval
        self.watch_target = watch_target
        self.treshold_for_tatget = float(threshold_for_target)
        # 최대 수집 반복 횟수
        self.iter_limit = iter_limit
        # 분류 헤더 cpu, memory, swap
        self.show_header = show_header
        self.header_only_once = header_only_once
        self.header_count = 0
        self.client = boto3.client('sqs')
        self.buffer = []
        self.max_size = 13


        # unit 여부
        self.show_units = show_units
        self.sep = sep
        # table col 너비
        self.col_width = 10

        self.time_field_width = max(self.col_width, len(time.strftime(date_format)) if date_format else 15)
        
        # 필요한 정보를 추출
        self.time_field_name = 'Timestamp' + (' (s)' if self.show_units else '') if date_format is None else 'Time'
        self.cpu_field_names = [
            'CPU' + (' (%)' if self.show_units else ''),
            'RAM' + (' (%)' if self.show_units else ''),
            'Swap' + (' (%)' if self.show_units else ''),
        ]
        self.platform = platform.system().lower()


    @property
    def tabular_format(self):
        fmt = '{:>' + str(self.time_field_width) + '} |'
        fmt += ('|{:>' + str(self.col_width) + '} ') * len(self.cpu_field_names)
        return fmt
    
    def process_alert(self, message) : 
        response = self.client.send_message(
            QueueUrl='https://sqs.ap-northeast-2.amazonaws.com/205930649271/alert_queue.fifo',
            MessageBody=message,
            MessageGroupId='alert_group',  # 그룹 ID 설정
            MessageDeduplicationId=str(uuid.uuid4()),  # 고유한 ID를 생성하여 중복 방지
        )

        response = self.client.send_message(
            QueueUrl='https://sqs.ap-northeast-2.amazonaws.com/205930649271/process_queue',
            MessageBody='process_queue',
            DelaySeconds=60,
            MessageAttributes={
                'Attribute1': {  # 'String' 대신 올바른 키 이름 사용
                    'StringValue': message,  # 문자열 값
                    'DataType': 'String'  # DataType은 반드시 'String', 'Number', 또는 'Binary'여야 함
                }
            }
        )


    def send_to_resource_queue(self, message) : 
        response = self.client.send_message(
            QueueUrl='https://sqs.ap-northeast-2.amazonaws.com/205930649271/monitoring',
            MessageBody='test-1',
            DelaySeconds=62,
            MessageAttributes={
                'Attribute1': {  # 'String' 대신 올바른 키 이름 사용
                    'StringValue': message,  # 문자열 값
                    'DataType': 'String'  # DataType은 반드시 'String', 'Number', 또는 'Binary'여야 함
                }
            }
        )

    def write_header(self):
        with smart_open(self.fname, 'a') as hf:
            cols = [self.time_field_name] + self.cpu_field_names
            print(self.tabular_format.format(*cols), file=hf)
            print('-' * (self.time_field_width + 1), end='', file=hf)
            print(
                '+',
                ('+' + '-' * (self.col_width + 1)) * len(self.cpu_field_names),
                sep='', end='', file=hf)
            print("\n", end='', file=hf)


    def poll_resource(self):
        cpu_resource = cpu_resources()
        mem_resource = memory_resorces()
        disk_resource = disk_resources()

        if self.watch_target == "CPU" :
            if cpu_resource[0] > self.treshold_for_tatget:
                return cpu_resource, mem_resource, disk_resource, get_process_cpu_usage()
            
            else:
                return cpu_resource, mem_resource, disk_resource, []
        elif self.watch_target == "MEMORY" :
            if mem_resource[0] > self.treshold_for_tatget:
                return cpu_resource, mem_resource, disk_resource, get_process_cpu_usage()
            
            else:
                return cpu_resource, mem_resource, disk_resource, []
        elif self.watch_target == "DISK": 
            if disk_resource[0] > self.treshold_for_tatget:
                return cpu_resource, mem_resource, disk_resource, get_process_cpu_usage()
            
            else:
                return cpu_resource, mem_resource, disk_resource, []
        else :
            return cpu_resource, mem_resource, disk_resource, []

    def add_buffer(self, data) :
        self.buffer.append(data)
        if len(self.buffer) >= self.max_size:
            self.send_to_resource_queue('\n'.join(self.buffer))
            self.process_buffer()

    def process_buffer(self):
        self.buffer.clear()  # 버퍼 비우기

    def write_record(self):
    # 기본 데이터 기록

        with smart_open(self.fname, 'a') as hf:
            stats = list(self.poll_resource())

            t = '{:.3f}'.format(time.time()) if self.date_format is None else time.strftime(self.date_format)
            cpu_percent = stats[0][0]
            percent_per_core = stats[0][1]
            
            ram_percent = stats[1][0]
            swap_percent = stats[1][1]
            ram_available = stats[1][2]

            disk_usage = stats[2][0]
            read_count = stats[2][1]
            write_count = stats[2][2]
            # byte 단위는 가늠이 어려우니까 MB 단위로 변환
            read_bytes = stats[2][3] / 1024 / 1024
            write_bytes = stats[2][4] / 1024 / 1024


            base_data = [t, cpu_percent, percent_per_core, ram_percent, swap_percent, ram_available, 
                         disk_usage, read_count, write_count, read_bytes, write_bytes]
            if self.style == 'csv':
                self.add_buffer(self.sep.join(map(str, base_data)))

            elif self.style == 'tabular':
                print(self.tabular_format.format(*base_data), file=hf)
            else:
                raise ValueError(f"Unrecognised style: {self.style}")

        # 프로세스 데이터 기록
        if stats[3]:  # 상위 프로세스가 있는 경우
            process_file = f"{self.fname}_processes.csv"  # 프로세스 정보를 기록할 파일
            message = ''
            with smart_open(process_file, 'a') as pf:
                for idx, proc in enumerate(stats[3]):
                    proc_data = [
                        t,  # 동일 타임스탬프
                        proc['pid'],  # 프로세스 ID
                        proc['name'],  # 프로세스 이름
                        proc['cpu_percent']  # CPU 사용량
                    ]
                    #print(self.sep.join(map(str, proc_data)), file=pf)
                    message = f"{message}\n {self.sep.join(map(str, proc_data))}"
                    if idx >= 4 :
                        self.process_alert(message)
                        break

    # 객체 자체도 호출할 수 있도록 다시 말해 Logger 객체 자체가 호출될 수 있도록 하는 메서드
    def __call__(self, n_iter=None):
        #if self.show_header and (self.header_count < 1 or not self.header_only_once):
        #    self.write_header()
        n_iter = self.iter_limit if n_iter is None else n_iter
        i_iter = 0
        while True:
            t_begin = time.time()
            self.write_record()
            i_iter += 1
            if n_iter is not None and n_iter > 0 and i_iter >= n_iter:
                break
            t_sleep = self.refresh_interval + t_begin - time.time() - 0.001
            if t_sleep > 0:
                time.sleep(t_sleep)


def main(**kwargs):
    logger = Logger(**kwargs)
    logger()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--loop', metavar='INTERVAL', dest='refresh_interval', type=float, default=1.0)
    parser.add_argument('-n', '--niter', metavar='MAXITER', dest='iter_limit', type=int, default=-1)
    parser.add_argument('--header', dest='show_header', action='store_true', default=True)
    parser.add_argument('-c', '--csv', dest='style', action='store_const', const='csv')
    parser.add_argument('-t', '--tabular', dest='style', action='store_const', const='tabular')
    parser.add_argument('-d', '--date-custom', dest='date_format', action='store')
    parser.add_argument('--no-units', dest='show_units', action='store_false', default=True)
    parser.add_argument('--fname', metavar='FILE', default=None, nargs='?')
    parser.add_argument('--watch', dest = "watch_target", default="CPU")
    parser.add_argument('--threshold', dest = "threshold_for_target", default=20)
    args = parser.parse_args()
    main(**vars(args))
