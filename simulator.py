import time

import random

def create_data():
    #randint生成整数
    #random.randint()
    #uniform生成浮点数
    voltage = random.uniform(0,3)
    return f"VOLT={voltage:.2f}"

def main():
    for _ in range(10):
        data = create_data()
        print(data)
        #停留1秒钟
        time.sleep(1)

if __name__ == "__main__":
    main()