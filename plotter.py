import csv

import matplotlib.pyplot as plt

times = []

voltages = []

with open("voltage_data.csv",
            "r", 
           encoding = "utf-8") as file:

    reader = csv.DictReader(file)

    for row in reader:
        times.append(row['time'])
        voltages.append(float(row["voltage"]))

    print(times)
    print(voltages)

'''以时间作为横轴、
 电压作为纵轴；
 marker="o" 会在每条数据的位置画一个圆点。'''
plt.plot(times, voltages, marker = 'o')

plt.title("Voltage Data")

plt.xlabel("Time")

plt.ylabel("Voltage(V)")

'''显示网格，方便判断电压大小。'''
plt.grid()

'''把横轴时间旋转45度，防止时间文字挤在一起。'''
plt.xticks(rotation=45)

'''自动调整图表边距，避免文字被窗口挡住。'''
plt.tight_layout()

plt.show()