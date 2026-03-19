@echo off
REM =============================================
REM  ★ Anaconda Prompt で実行してください ★
REM
REM  手順:
REM    1. スタートメニューで「Anaconda Prompt」を検索して開く
REM    2. このファイルをその黒い画面にドラッグ＆ドロップ
REM    3. Enter を押す
REM =============================================

echo.
echo  XROSS exe ビルド開始
echo.

cd /d "%~dp0.."
pip install pyinstaller numpy pandas matplotlib scikit-learn
pip install -e .
python build_exe\build.py --backend pyinstaller --onefile

echo.
if exist "dist\XROSS.exe" (
    echo  ビルド成功！ → dist\XROSS.exe
) else (
    echo  ビルド失敗。上のエラーメッセージを確認してください。
)
echo.
pause
