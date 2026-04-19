import pandas as pd

# 读取Excel文件
df = pd.read_excel('SmartTV_AutoFullTestCase_TV_Screenshot.xlsx')

# 只处理runOption为Y的行
df = df[df['runOption'] == 'Y']

# 打印前5行的testID和checkPic值
print('前5行的testID和checkPic值:')
print(df[['testID', 'checkPic']].head(5))

# 模拟后端处理逻辑
valid_rows = []
for index, row in df.iterrows():
    # 检查oriStep和preScript列
    ori_step = str(row.get('oriStep', '')).strip()
    pre_script = str(row.get('preScript', '')).strip()
    
    if not ori_step and not pre_script:
        continue
    
    # 获取testID
    title = ''
    if 'testID' in row:
        test_id_value = row['testID']
        if test_id_value is not None and str(test_id_value).strip() != '' and str(test_id_value).strip() != 'nan':
            title = str(test_id_value).strip()
    
    # 获取checkPic
    verify_image = ''
    if 'checkPic' in row:
        check_pic_value = row['checkPic']
        if check_pic_value is not None and str(check_pic_value).strip() != '' and str(check_pic_value).strip() != 'nan':
            verify_image = str(check_pic_value).strip()
    
    # 添加到valid_rows
    valid_rows.append({"row": index+2, "title": title, "verify_image": verify_image, "oriStep": ori_step, "preScript": pre_script})

# 打印前5个valid_rows
print('\n前5个valid_rows:')
for row in valid_rows[:5]:
    print(row)