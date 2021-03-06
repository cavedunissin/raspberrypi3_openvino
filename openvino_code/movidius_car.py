#!/usr/bin/env python3
import argparse
import time

import cv2
import numpy as np
from openvino.inference_engine import IENetwork, IEPlugin
import RPi.GPIO as GPIO

# 設定腳位
PWM_PIN_left_1 = 5
PWM_PIN_left_2 = 6
PWM_PIN_right_3 = 13
PWM_PIN_right_4 = 19

IR_LEFT_PIN = 17
IR_MIDDLE_PIN = 27
IR_RIGHT_PIN = 22

DUTY_CYCLE = 65


def main():
    # 設定程式參數
    arg_parser = argparse.ArgumentParser(description='軌跡車程式')
    arg_parser.add_argument(
        '--model-file',
        required=True,
        help='模型檔架構檔',
    )
    arg_parser.add_argument(
        '--weights-file',
        required=True,
        help='模型檔參數檔',
    )
    arg_parser.add_argument(
        '--input-width',
        type=int,
        default=48,
        help='模型輸入影像寬度',
    )
    arg_parser.add_argument(
        '--input-height',
        type=int,
        default=48,
        help='模型輸入影像高度',
    )

    # 解讀程式參數
    args = arg_parser.parse_args()
    assert args.input_width > 0 and args.input_height > 0

    # 設置 Movidius 裝置
    plugin = IEPlugin(device='MYRIAD')

    # 載入模型檔
    net = IENetwork.from_ir(model=args.model_file, weights=args.weights_file)
    input_blob = next(iter(net.inputs))
    out_blob = next(iter(net.outputs))
    exec_net = plugin.load(network=net)

    # 開啓影片來源
    video_dev = cv2.VideoCapture(0)

    # 初始化 GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
	
    GPIO.setup(IR_RIGHT_PIN, GPIO.IN)  #GPIO 17 -> Left IR in
    GPIO.setup(IR_MIDDLE_PIN, GPIO.IN) #GPIO 27 -> Cent IR in
    GPIO.setup(IR_LEFT_PIN, GPIO.IN)   #GPIO 22 -> Right IR in

    GPIO.setup(PWM_PIN_left_1, GPIO.OUT)
    GPIO.setup(PWM_PIN_left_2, GPIO.OUT)
    GPIO.setup(PWM_PIN_right_3, GPIO.OUT)
    GPIO.setup(PWM_PIN_right_4, GPIO.OUT)

    pwm_left_1 = GPIO.PWM(PWM_PIN_left_1, 500)
    pwm_left_2 = GPIO.PWM(PWM_PIN_left_2, 500)
    pwm_right_3 = GPIO.PWM(PWM_PIN_right_3, 500)
    pwm_right_4 = GPIO.PWM(PWM_PIN_right_4, 500)

    pwm_left_1.start(0)
    pwm_left_2.start(0)
    pwm_right_3.start(0)
    pwm_right_4.start(0)

    def recognize_image():

        # 先丟掉前十張舊的辨識結果
        for i in range(10):
            image = video_dev.read()

        ret, orig_image = video_dev.read()
        assert ret is not None

        # 縮放爲模型輸入的維度、調整數字範圍爲 0～1 之間的數值
        preprocessed_image = cv2.resize(
            orig_image.astype(np.float32),
            (args.input_width, args.input_height),
        ) / 255.0

        # 這步驟打包圖片成大小爲 1 的 batch
        batch = np.expand_dims(
            np.transpose(preprocessed_image, (2, 0 ,1)),  # 將維度順序從 NHWC 調整爲 NCHW
            0,
        )

        # 執行預測
        request_handle = exec_net.start_async(
            request_id=0,
            inputs={input_blob: batch}
        )
        status = request_handle.wait()
        result_batch = request_handle.outputs[out_blob]
        result_onehot = result_batch[0]

        # 判定結果
        class_id = np.argmax(result_onehot)
        left_score, right_score, stop_score, other_score = result_onehot

        print('預測：%.2f %.2f %.2f %.2f' % (left_score, right_score, stop_score, other_score))

        # print(result_onehot)
        if class_id == 0:
            return 'left'
        elif class_id == 1:
            return 'right'
        elif class_id == 2:
            return 'stop'
        elif class_id == 3:
            return 'other'

    def forward():
        pwm_left_1.ChangeDutyCycle(DUTY_CYCLE)
        pwm_left_2.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(DUTY_CYCLE)
        pwm_right_4.ChangeDutyCycle(0)

    def head_left():
        pwm_left_1.ChangeDutyCycle(0)
        pwm_left_2.ChangeDutyCycle(DUTY_CYCLE)
        pwm_right_3.ChangeDutyCycle(DUTY_CYCLE)
        pwm_right_4.ChangeDutyCycle(0)

    def head_right():
        pwm_left_1.ChangeDutyCycle(DUTY_CYCLE)
        pwm_left_2.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        pwm_right_4.ChangeDutyCycle(DUTY_CYCLE)

    def stop():
        pwm_left_1.ChangeDutyCycle(0)
        pwm_left_2.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        pwm_right_4.ChangeDutyCycle(0)

    def cross_left():
        time.sleep(1)

        pwm_left_1.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(100)
        time.sleep(0.3)

        pwm_left_1.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        time.sleep(0.6)

        pwm_left_1.ChangeDutyCycle(100)
        pwm_right_3.ChangeDutyCycle(100)
        time.sleep(0.55)

        pwm_left_1.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        time.sleep(0.5)

    def cross_right():
        time.sleep(1)

        pwm_left_1.ChangeDutyCycle(100)
        pwm_right_3.ChangeDutyCycle(0)
        time.sleep(0.3)

        pwm_left_1.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        time.sleep(0.6)

        pwm_left_1.ChangeDutyCycle(100)
        pwm_right_3.ChangeDutyCycle(100)
        time.sleep(0.55)

        pwm_left_1.ChangeDutyCycle(0)
        pwm_right_3.ChangeDutyCycle(0)
        time.sleep(0.5)

    def track_line():
        middle_val = GPIO.input(IR_MIDDLE_PIN)
        left_val = GPIO.input(IR_LEFT_PIN)
        right_val = GPIO.input(IR_RIGHT_PIN)
        print('光感:', left_val, middle_val, right_val)

        if middle_val:
            if left_val and right_val:        # 白白白
                return 'stop'
            elif left_val and not right_val:  # 白白黑
                return 'left'
            elif not left_val and right_val:  # 黑白白
                return 'right'
            else:
                return 'forward'              # 黑白黑
        else:
            if left_val and right_val:        # 白黑白
                return 'stall'
            elif left_val and not right_val:  # 白黑黑
                return 'left'
            elif not left_val and right_val:  # 黑黑白
                return 'right'
            else:                             # 黑黑黑
                return 'stall'

    try:
        while True:
            advice = track_line()

            if advice == 'left':
                print('動作:', '左轉')
                head_left()

            elif advice == 'right':
                print('動作:', '右轉')
                head_right()

            elif advice == 'stop':
                print('動作:', '停止')
                stop()

                sign = recognize_image()

                if sign == 'left':
                    print('影像:', '左轉標誌')
                    cross_left()

                elif sign == 'right':
                    print('影像:', '右轉標誌')
                    cross_right()

                elif sign == 'stop':
                    print('影像:', '停止標誌')

                elif sign == 'other':
                    print('影像:', '無標誌')

            elif advice == 'forward':
                print('動作:', '前進')
                forward()

            elif advice == 'stall':
                print('動作:', '前進')
                forward()

            print()

    except KeyboardInterrupt:
        print('使用者中斷')

    # 終止馬達
    pwm_left_1.stop(0)
    pwm_left_2.stop(0)
    pwm_right_3.stop(0)
    pwm_right_4.stop(0)

    # 終止影像裝置
    video_dev.release()


if __name__  == '__main__':
    main()
