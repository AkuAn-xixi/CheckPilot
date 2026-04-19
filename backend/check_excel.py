import pandas as pd

# 读取Excel文件
df = pd.read_excel('SmartTV_AutoFullTestCase_TV_Screenshot.xlsx')

# 打印列名
print('Excel文件列名:')
for col in df.columns:
    print(f'  - {col}')

# 打印前5行数据
print('\n前5行数据:')
print(df.head())

# 检查特定列是否存在
print('\n检查特定列是否存在:')
print(f'  testID列存在: {"testID" in df.columns}')
print(f'  checkPic列存在: {"checkPic" in df.columns}')
print(f'  oriStep列存在: {"oriStep" in df.columns}')
print(f'  preScript列存在: {"preScript" in df.columns}')