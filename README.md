# Nickey44A-PAD 用 yuPad43 ファームウェア

使っている配線に合わせて、どちらか一方の ZIP をダウンロードしてください。どちらも右側が親機で、ZIP には左右それぞれの UF2 が入っています。

| 対象 | パッドの構成 | ダウンロード |
| --- | --- | --- |
| Nixさんの純正構成 | 右に1枚。カーソル慣性はオフ、2本指スクロールの慣性はオン | [Nix 用 ZIP](https://github.com/yuchamichami/yupad43-nickey44a/releases/latest/download/nickey44a-nix.zip) |
| atsさんの手配線構成 | 左右に1枚ずつ。カーソル慣性はオン、スクロール慣性はオフ。右は縦スクロール、左は縦横スクロールに対応 | [ats 用 ZIP](https://github.com/yuchamichami/yupad43-nickey44a/releases/latest/download/nickey44a-ats.zip) |

## 書き込み

1. ZIP を展開します。元のファームに戻せるよう、今使っている左右の UF2 も手元に残しておいてください。
2. 左側を USB でつなぎ、RESET を素早く2回押します。表示されたドライブに `-left.uf2` をコピーします。
3. 右側も同じ手順で `-right.uf2` を書き込みます。右側をPCにつなぎ、左右のキーとパッドを試してください。

## ファームの内容

それぞれのキー配列、パッドの向き、ZMK Studio の設定を引き継ぎました。Nix 版はスクロール量を従来の 75% に、ats 版はレイヤーごとの速度設定を引き継いでいます。両版とも、センサー起動時の通信再試行、ドラッグ解除の取りこぼし対策、3本指をずらして離すときの中クリック判定、微小なスクロール量の処理を反映しています。

共通ドライバは XIAO と yuPad43 の組み合わせで実機確認済みです。Nickey44A-PAD の左右4ファイルはビルドし、ピン配置・回転方向・左右の役割・UF2 の内容を検査しました。Nickey44A-PAD 実機での左右間通信は今回の確認範囲外です。

## ビルド

GitHub Actions の **Build Nickey44A firmware** で両構成をビルドできます。ビルド環境と手順は [ワークフロー](.github/workflows/build.yml) と [build.sh](build.sh) にあります。同じ環境で片方だけビルドする場合は、作成先に新しいディレクトリ名を指定します。

```sh
./build.sh nix /tmp/nickey-nix
./build.sh ats /tmp/nickey-ats
```

UF2 は各ディレクトリの `output/` に出力されます。各 ZIP の `SHA256SUMS` でファイルを照合できます。

元の設定は [Nixさんの yuPad43 ブランチ](https://github.com/nixiy/zmk-config-nickey44a-pad/tree/5980dbcf70c2bbbe9a4953bbc63c516a0f6caec8) と [atsさんの手配線版](https://github.com/freedom96960324/zmk-config-nickey44a-pad/tree/38e8079b911539dabdcc4838cdbbbf14e2a9150f) です。変更箇所は [profiles](profiles)、使用したドライバは [zmk-driver-yupad43](https://github.com/yuchamichami/zmk-driver-yupad43/tree/58e590adbe448924ac104747ee6366d79f16d04c) で確認できます。
