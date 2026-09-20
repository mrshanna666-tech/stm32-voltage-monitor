import csv
from pathlib import Path


CSV_FILE = Path(__file__).with_name("voltage_data.csv")


def analyze_data():
    voltages = []
    warning_count = 0

    if not CSV_FILE.exists():
        print("没有找到 voltage_data.csv")
        return None

    with open(
        CSV_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            try:
                voltage = float(row["voltage"])
            except (KeyError, TypeError, ValueError):
                # 遇到损坏或不完整的数据时跳过
                continue

            voltages.append(voltage)

            status = row.get("status", "").strip().upper()

            if status == "WARNING":
                warning_count += 1

    if not voltages:
        print("CSV中没有有效的电压数据")
        return None

    total_count = len(voltages)
    normal_count = total_count - warning_count
    warning_rate = warning_count / total_count * 100

    return {
        "count": total_count,
        "average": sum(voltages) / total_count,
        "maximum": max(voltages),
        "minimum": min(voltages),
        "normal_count": normal_count,
        "warning_count": warning_count,
        "warning_rate": warning_rate
    }


def print_report(result):
    if result is None:
        return

    print("\n========== 电压数据分析报告 ==========")
    print(f"数据总数：{result['count']}")
    print(f"平均电压：{result['average']:.2f} V")
    print(f"最大电压：{result['maximum']:.2f} V")
    print(f"最小电压：{result['minimum']:.2f} V")
    print(f"正常次数：{result['normal_count']}")
    print(f"警告次数：{result['warning_count']}")
    print(f"警告比例：{result['warning_rate']:.2f}%")
    print("=====================================")


def main():
    result = analyze_data()
    print_report(result)


if __name__ == "__main__":
    main()