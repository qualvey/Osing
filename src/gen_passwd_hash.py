import bcrypt


# 1. 在这里输入你想为用户设置的明文密码
clear_password = "Passwd@911"

# 2. 原生 bcrypt 接收的是 bytes，所以需要把字符串 encode() 一下
# gensalt() 会自动生成随机盐并进行哈希
hashed_bytes = bcrypt.hashpw(clear_password.encode('utf-8'), bcrypt.gensalt())

# 3. 将字节转换为字符串，方便你复制到数据库
hashed_password = hashed_bytes.decode('utf-8')

print("--- 请复制下方这串密文，填入数据库的 password_hash 字段中 ---")
print(hashed_password)
# 输出长这样：$2b$12$4KmxoIexG... (每次生成都不同，这是正常的)