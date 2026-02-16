@echo off
echo 🪖 Asterix Chart Generator
echo 📊 Publication-Quality Chart Creation
echo.

:: Check if CSV file exists
if not exist "summary_data.csv" (
    echo ❌ Error: summary_data.csv not found!
    echo.
    echo Please:
    echo 1. Export your Summary tab as CSV
    echo 2. Save it as 'summary_data.csv' in this folder
    echo 3. Run this script again
    echo.
    pause
    exit /b
)

:: Create project folder with timestamp
for /f "tokens=1-4 delims=/ " %%i in ('date /t') do set mydate=%%i_%%j_%%k
for /f "tokens=1-2 delims=: " %%i in ('time /t') do set mytime=%%i%%j
set mytime=%mytime: =%
set foldername=Project_%mydate%_%mytime%

echo 📁 Creating project folder: %foldername%
mkdir "%foldername%"

:: Copy CSV to project folder
copy "summary_data.csv" "%foldername%\summary_data.csv" > nul

:: Run chart generator in project folder
cd "%foldername%"
echo 📈 Generating charts...
python ..\chart_generator.py

:: Clean up - remove CSV from main folder
cd ..
del "summary_data.csv" > nul

echo.
echo ✅ Project complete!
echo 📁 Your charts are in: %foldername%\asterix_charts\
echo 📊 CSV backup saved in: %foldername%\
echo 🚀 Ready for next project!
echo.
pause
