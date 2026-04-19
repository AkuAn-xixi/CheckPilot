import pandas as pd

# 读取Excel文件
df = pd.read_excel('SmartTV_AutoFullTestCase_TV_Screenshot.xlsx')

# 只处理runOption为Y的行
df = df[df['runOption'] == 'Y']

# 检查testID和checkPic列的值
print('检查testID和checkPic列的值:')
print(f'  testID列非空值数量: {df["testID"].notna().sum()}')
print(f'  testID列空值数量: {df["testID"].isna().sum()}')
print(f'  checkPic列非空值数量: {df["checkPic"].notna().sum()}')
print(f'  checkPic列空值数量: {df["checkPic"].isna().sum()}')

# 打印前10行的testID和checkPic值
print('\n前10行的testID和checkPic值:')
print(df[['testID', 'checkPic']].head(10))

# 检查oriStep和preScript列的值
print('\n检查oriStep和preScript列的值:')
print(f'  oriStep列非空值数量: {df["oriStep"].notna().sum()}')
print(f'  oriStep列空值数量: {df["oriStep"].isna().sum()}')
print(f'  preScript列非空值数量: {df["preScript"].notna().sum()}')
print(f'  preScript列空值数量: {df["preScript"].isna().sum()}')