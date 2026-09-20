import csv

import time

from datetime import datetime

from simulator import create_data

from parse import parse_data

from pathlib import Path


CSV_FILE = Path(__file__).with_name("voltage_data.csv")


def save_data(voltage, status="NORMAL"):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 文件不存在或内容为空时，需要写入表头
    need_header = (
        not CSV_FILE.exists()
        or CSV_FILE.stat().st_size == 0
    )

    with open(
        CSV_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        if need_header:
            writer.writerow([
                "time",
                "voltage",
                "status"
            ])

        writer.writerow([
            current_time,
            f"{voltage:.2f}",
            status
        ])
def main():


    for _ in range(10):
        raw_data = create_data()
    
        parse_result = parse_data(raw_data)

        if parse_result is not None:
                save_data(parse_result)
                print(f"Saved: {parse_result}V")

        time.sleep(1)

        
if __name__ == "__main__":
    main()
