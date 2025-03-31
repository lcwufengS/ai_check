# -*- coding: utf-8 -*-
import os
import codecs
import shutil

def convert_file(file_path):
    """将文件从ISO-8859-1编码转换为UTF-8编码，并添加编码声明"""
    # 读取文件内容（使用ISO-8859-1编码）
    with codecs.open(file_path, 'r', 'iso-8859-1') as f_in:
        content = f_in.read()
    
    # 检查文件是否已有编码声明
    if not content.startswith('# -*- coding: utf-8 -*-'):
        content = '# -*- coding: utf-8 -*-\n' + content
    
    # 创建备份
    backup_path = file_path + '.bak'
    shutil.copy2(file_path, backup_path)
    
    # 写入文件（使用UTF-8编码）
    with codecs.open(file_path, 'w', 'utf-8') as f_out:
        f_out.write(content)
    
    print(f'已转换: {file_path}')

def main():
    # 项目根目录
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 处理所有Python文件
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                convert_file(file_path)

if __name__ == '__main__':
    main()
    print('所有Python文件编码转换完成！')