from simulator import create_data

def parse_data(data):

    clean_data = data.strip()
    #clean_data.count计算出现了多少个等号
    if clean_data.count("=") != 1:
        print("Invalid data format!")
        return None


    data_type, value_text = clean_data.split("=")

    if data_type != "VOLT":
        print("Invalid data type!")
        return None

    try:
        voltage = float(value_text)
    except ValueError:
        print("Invalid voltage value!")
        return None

    if voltage < 0 or voltage > 3.3:
        print("Voltage out of range!")
        return None

    return voltage

def main():
    data = create_data()
    voltage = parse_data(data)

    if voltage is not None:
        print(f"解析后的电压：{voltage}V")

    
if __name__ == "__main__":
    main()



