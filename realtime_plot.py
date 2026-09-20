from collections import deque

import matplotlib.pyplot as plt

from simulator import create_data
from parse import parse_data
from recorder import save_data


# 最多显示最近50个数据点
MAX_POINTS = 50

# 电压报警阈值
WARNING_THRESHOLD = 2.5

# 每次采样间隔，单位：秒
SAMPLE_INTERVAL = 0.5


def main():
    # deque和列表类似，但超过最大长度后会自动删除最早的数据
    sample_numbers = deque(maxlen=MAX_POINTS)
    voltages = deque(maxlen=MAX_POINTS)

    sample_count = 0

    # 尽可能正常显示中文
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    # 开启交互模式
    plt.ion()

    fig, ax = plt.subplots()

    # 创建电压曲线
    line, = ax.plot(
        [],
        [],
        color="blue",
        marker="o",
        markersize=4,
        label="电压"
    )

    # 添加2.5V警戒线
    ax.axhline(
        y=WARNING_THRESHOLD,
        color="red",
        linestyle="--",
        label="警戒线 2.5V"
    )

    ax.set_title("STM32 电压实时监控")
    ax.set_xlabel("采样次数")
    ax.set_ylabel("电压（V）")
    ax.set_ylim(0, 3.3)
    ax.grid(True)
    ax.legend()

    # 左上角的信息文字
    information = ax.text(
        0.02,
        0.95,
        "",
        transform=ax.transAxes,
        verticalalignment="top"
    )

    try:
        while plt.fignum_exists(fig.number):
            # 1. 生成模拟串口数据，例如 VOLT=2.73
            raw_data = create_data()

            # 2. 将字符串解析成浮点数
            voltage = parse_data(raw_data)

            if voltage is None:
                print(f"无法解析：{raw_data}")
                continue


            # 4. 保存到实时曲线使用的队列
            sample_count += 1
            sample_numbers.append(sample_count)
            voltages.append(voltage)

            # 5. 计算统计数据
            average_voltage = sum(voltages) / len(voltages)
            maximum_voltage = max(voltages)
            minimum_voltage = min(voltages)

            if voltage >= WARNING_THRESHOLD:
                status = "WARNING"
                display_status = "警告：电压过高"
                status_color = "red"
                line.set_color("red")
            else:
                status = "NORMAL"
                display_status = "状态正常"
                status_color = "green"
                line.set_color("blue")

# 判断出状态后再保存
            save_data(voltage, display_status)

            print(
                f"第{sample_count}次采样："
                f"{voltage:.2f}V，{display_status}"
            )

            # 7. 更新曲线
            line.set_data(
                list(sample_numbers),
                list(voltages)
            )

            # 更新横坐标范围
            if sample_count < MAX_POINTS:
                ax.set_xlim(0, MAX_POINTS)
            else:
                ax.set_xlim(
                    sample_count - MAX_POINTS + 1,
                    sample_count + 1
                )

            # 更新左上角信息
            information.set_text(
                f"当前电压：{voltage:.2f} V\n"
                f"平均电压：{average_voltage:.2f} V\n"
                f"最大电压：{maximum_voltage:.2f} V\n"
                f"最小电压：{minimum_voltage:.2f} V\n"
                f"{display_status}"
            )

            information.set_color(status_color)

            # 重新绘制
            fig.canvas.draw_idle()
            plt.pause(SAMPLE_INTERVAL)

    except KeyboardInterrupt:
        print("\n用户停止程序")

    finally:
        plt.ioff()
        plt.close("all")
        print("实时监控已关闭")


if __name__ == "__main__":
    main()