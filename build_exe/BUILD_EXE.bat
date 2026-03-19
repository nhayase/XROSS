@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo.
echo  =============================================
echo   XROSS Executable Builder
echo  =============================================
echo.

REM =============================================================
REM  Anaconda を有効化する
REM  
REM  Anaconda は通常の cmd.exe から python が使えない。
REM  conda.bat を呼び出して base 環境を有効化する必要がある。
REM =============================================================

set "CONDA_BAT="

REM 方法1: conda が既に使える場合（Anaconda Prompt から実行した場合）
where conda >nul 2>&1
if not errorlevel 1 (
    echo  [OK] conda は既に有効です。
    goto :conda_ready
)

REM 方法2: よくあるインストール先の condabin\conda.bat を探す
for %%D in (
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\Anaconda3"
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\Miniconda3"
    "C:\ProgramData\anaconda3"
    "C:\ProgramData\Anaconda3"
    "C:\ProgramData\miniconda3"
    "C:\anaconda3"
    "C:\Anaconda3"
    "C:\miniconda3"
    "C:\Miniconda3"
    "C:\tools\anaconda3"
    "C:\tools\miniconda3"
) do (
    if exist "%%~D\condabin\conda.bat" (
        set "CONDA_BAT=%%~D\condabin\conda.bat"
        goto :found_conda_bat
    )
    if exist "%%~D\Scripts\conda.exe" (
        set "CONDA_BAT=%%~D\condabin\conda.bat"
        if exist "!CONDA_BAT!" goto :found_conda_bat
        REM Scripts\activate.bat で代用
        if exist "%%~D\Scripts\activate.bat" (
            echo  [INFO] Anaconda 検出: %%~D
            call "%%~D\Scripts\activate.bat" "%%~D"
            goto :conda_ready
        )
    )
)

REM 方法3: py launcher / 通常の python
py -3 --version >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] Python Launcher (py -3) を使用します。
    set "PYTHON_CMD=py -3"
    goto :python_ready
)

python --version >nul 2>&1
if not errorlevel 1 (
    echo  [INFO] python (PATH) を使用します。
    set "PYTHON_CMD=python"
    goto :python_ready
)

REM 方法4: 直接パス検索
for %%V in (313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        echo  [INFO] Python 検出: !PYTHON_CMD!
        goto :python_ready
    )
)

REM ---- 全て失敗 ----
echo.
echo  =============================================
echo  [ERROR] Python/Anaconda が見つかりません。
echo  =============================================
echo.
echo  ■ Anaconda をインストール済みの場合:
echo.
echo    このファイルをダブルクリックするのではなく、
echo    以下の手順で実行してください:
echo.
echo    1. スタートメニューから「Anaconda Prompt」を開く
echo    2. 以下の3行をコピーして貼り付けて Enter:
echo.
echo       cd /d "%~dp0.."
echo       pip install pyinstaller
echo       python build_exe\build.py --backend pyinstaller --onefile
echo.
echo    3. 完了後、dist\XROSS.exe が生成されます。
echo.
echo  ■ Python 未インストールの場合:
echo    https://www.python.org/downloads/ からインストール
echo    ※ "Add python.exe to PATH" に必ずチェック
echo.
pause
exit /b 1

:found_conda_bat
echo  [INFO] Anaconda 検出: !CONDA_BAT!
echo  [INFO] conda activate base を実行中...
call "!CONDA_BAT!" activate base
if errorlevel 1 (
    echo  [WARN] conda activate 失敗。直接 python を試行...
)

:conda_ready
set "PYTHON_CMD=python"

:python_ready

REM =============================================================
REM  Python 動作確認
REM =============================================================
!PYTHON_CMD! --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] python の実行に失敗しました。
    echo.
    echo  Anaconda Prompt から手動で実行してください:
    echo    cd /d "%~dp0.."
    echo    pip install pyinstaller
    echo    python build_exe\build.py --backend pyinstaller --onefile
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('!PYTHON_CMD! --version 2^>^&1') do echo  [OK] %%i
echo.

REM =============================================================
REM  Step 1: pip install
REM =============================================================
echo  [Step 1/3] パッケージインストール中...

echo    - pip 更新中...
!PYTHON_CMD! -m pip install --upgrade pip -q >nul 2>&1

echo    - pyinstaller インストール中...
!PYTHON_CMD! -m pip install pyinstaller -q
if errorlevel 1 (
    echo  [ERROR] pyinstaller のインストールに失敗。
    echo  ネットワーク接続を確認してください。
    pause
    exit /b 1
)

echo    - XROSS の依存パッケージをインストール中...
!PYTHON_CMD! -m pip install numpy pandas matplotlib scikit-learn -q >nul 2>&1

echo    - XROSS パッケージをインストール中...
pushd "%~dp0.."
!PYTHON_CMD! -m pip install -e . -q >nul 2>&1
if errorlevel 1 (
    !PYTHON_CMD! -m pip install . -q >nul 2>&1
)
popd

echo    完了。
echo.

REM =============================================================
REM  Step 2: Build
REM =============================================================
echo  [Step 2/3] XROSS.exe をビルド中...
echo    （初回は 5〜15 分かかります）
echo.

!PYTHON_CMD! "%~dp0build.py" --backend pyinstaller --onefile

if errorlevel 1 (
    echo.
    echo  [ERROR] ビルド失敗。
    echo.
    echo  よくある原因:
    echo    - ウイルス対策ソフトがブロック → 一時無効化
    echo    - 管理者権限が必要 → 右クリック→管理者として実行
    echo.
    pause
    exit /b 1
)

REM =============================================================
REM  Step 3: Done
REM =============================================================
echo.
echo  [Step 3/3] 完了！

set "EXE=%~dp0..\dist\XROSS.exe"
if exist "!EXE!" (
    for %%A in ("!EXE!") do set /a "MB=%%~zA / 1048576"
    echo.
    echo  =============================================
    echo   出力:   dist\XROSS.exe
    echo   サイズ: 約 !MB! MB
    echo  =============================================
    echo.
    echo  XROSS.exe をダブルクリックすると起動します。
) else (
    echo  [WARN] dist\XROSS.exe が見つかりません。
    echo  dist フォルダを確認してください。
)

echo.
pause
