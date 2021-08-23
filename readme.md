# 自治体をJSONにするだけのスクリプト
## 導入
1. ```pip install -r requirements.txt```で必要な環境にする
2. ```python parse.py```を実行
3. ```manicipalities.json```が生成される.

## 注意
* wikipediaのページをもってくる仕様。一度もってきたらファイルで保存し、ファイルが有ればそれを読むようにしているので連続して実行しても問題ない。
* 生成したjsonは[拙作][1]で使用可能です。

[1]:https://github.com/littleIkawa/tagging_box