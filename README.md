# 개요

  > ## ***현재 5000원인 코인이 4000원이 된다면 50개 팔고 싶다***

  - **코인원에서 시장가보다 낮은 가격으로는 예약 매도가 안되서 만든 파이썬 스크립트**
    - ~~그냥 예약 매도되는 거래소를 이용하자~~
  -	특정 통화의 거래금액(시장가)이 지정금액 이하가 되면 매도를 시도
  -	일정한 시간이 지나도 매도가 이루어지지 않으면, 매도를 취소하고 시장가를 구하는 것부터 반복
  -	매도에 성공하면 프로그램을 종료


# 필요한 것
  - [Python3.6 (64bit)](https://www.python.org/downloads/)
  - [코인원 API V2 키](https://coinone.co.kr/developer/app/)
    - API 버전은 **V2** 선택
    - **'거래소 조회'** 와 **'거래소 주문'** 의 권한 선택


#	실행
  ```
  pip install -r requirements.txt
  python coinone_reserve_sell.py config.json
  ```


#	config.json
  - **여기 없는 항목은 기본값 사용**
  - access_token
	 -	코인원에서 발급받은 access_token
  - secret_key
	 -	코인원에서 발급받은 secret_key
  - reservation
    - currency
        - `btc, bch, eth, etc, xrp, qtum, iota, ltc` 중 하나
    -	sell_threshold
        - 가격 이하가 되면 매도 시도
    -	sell_margin_price
        - 매도할 때 시장가에서 뺄 금액
          - `매도가격 = 시장가 - sell_margin_price`
    -	sell_quantity
        - 매도 수량 (소수점)
    - sell_wait_sec
        - 매도를 시도하고 완료까지 대기할 시간(초), 오차 약 10초
  - 기타
    - 숫자가 아닌 문자는 쌍따옴표(") 로 감싸야 한다
      - `"currency": "iota"` 또는 `"sell_threshold": 1000`
    - sell_margin_price 가 음수면 시장가보다 높은 가격으로 매도
      - 이 방법을 사용해서 프로그램을 테스트 할 수 있다

# 설정 예
   > **라이트코인(ltc)이 150000원 이하가 되면, 1.5개를 140000원으로 약 1분 동안 매도 시도**
  ```json
     "reservation": [{
          "currency": "ltc",
          "sell_threshold": 150000,
          "sell_margin_price": 10000,
          "sell_quantity": 1.5,
          "sell_wait_sec": 60
          }
      ]
  ```

# 테스트
  - 2018-02-24
    - sell_margin_price 를 음수로 해서, 시장가보다 높은 가격으로 매도가 걸리는 것을 확인
    - sell_wait_sec 이후에 매도를 취소하는 것을 확인
    - 매도 취소 후, 시장가를 구해서 프로그램을 반복함을 확인
    - 매도가 되고, 프로그램이 종료되는지는 미확인
