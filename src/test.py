from Settings import settings

def main():
# 假定你在根目录下已经创建了 config.json
    try:


        print(settings.domain)
    except Exception as error:
        print(f"程序运行出错: {error}")
        
main()