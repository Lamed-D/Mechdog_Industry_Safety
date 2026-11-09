# 사용자가 robot/vision.py를 vision.py로 장치 최상위에 준비한 뒤 REPL에서 실행합니다.
# 기존 main.py와 카메라 펌웨어를 덮어쓰지 않습니다. 성공은 낙상 감지 검증이 아닙니다.


def main():
    import Hiwonder_IIC
    from vision import Vision
    result = Vision(Hiwonder_IIC).read_face()
    print(result)
    return result


if __name__ == "__main__":
    main()
