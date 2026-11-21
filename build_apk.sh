#!/bin/sh
# 编译大肥鱼桌面 APK（无需 Gradle，aapt + javac + dx + apksigner）
set -e

# 签名口令从环境变量读，不要写死在脚本里
#   export KS_PASS='你自己的口令'
KS_PASS="${KS_PASS:?请先设置 KS_PASS 环境变量}"
cd /d/workbuddy/2026-11-19-10-59-25

SDK=sdk_dl
JAVA_HOME="$(pwd)/$SDK/jdk-17.0.2"
BT="$(pwd)/$SDK/bt/android-8.1.0"
ANDROID_JAR="$(pwd)/$SDK/plat/android-8.1.0/android.jar"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

cd apk
rm -rf build gen base.apk app-unsigned.apk app.apk
mkdir -p build/classes gen

echo "[1/5] 打包资源与清单"
"$BT/aapt.exe" package -f -M AndroidManifest.xml -I "$ANDROID_JAR" -A assets -F base.apk

echo "[2/5] 编译 Java"
find src -name "*.java" > build/sources.txt
javac --release 8 -encoding UTF-8 -classpath "$ANDROID_JAR" -d build/classes @build/sources.txt
find build/classes -name "*.class" | head -5

echo "[3/5] 转 dex"
"$JAVA_HOME/bin/java.exe" -cp "$BT/lib/dx.jar" com.android.dx.command.Main --dex --output=build/classes.dex build/classes

echo "[4/5] 合成 APK"
cp base.apk app-unsigned.apk
cd build
"$JAVA_HOME/bin/jar.exe" uf ../app-unsigned.apk classes.dex 2>/dev/null || \
  "$JAVA_HOME/bin/java.exe" -cp "$JAVA_HOME/lib/tools.jar" sun.tools.jar.Main uf ../app-unsigned.apk classes.dex 2>/dev/null || true
cd ..
# 兜底：用 python 把 dex 塞进 apk
"C:/Users/zlw/.workbuddy/binaries/python/envs/default/Scripts/python.exe" - <<'PY'
import zipfile, shutil, os
src = "app-unsigned.apk"; dst = "app-unsigned2.apk"
with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
    for it in zi.infolist():
        if it.filename == "classes.dex": continue
        zo.writestr(it, zi.read(it.filename))
    zo.write("build/classes.dex", "classes.dex")
shutil.move(dst, src)
z = zipfile.ZipFile(src); print("   apk entries:", len(z.namelist()), "dex?", "classes.dex" in z.namelist())
PY

echo "[5/5] 签名"
if [ ! -f dafeiyu.keystore ]; then
  keytool -genkeypair -keystore dafeiyu.keystore -alias dfy -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass "$KS_PASS" -keypass "$KS_PASS" \
    -dname "CN=DaFeiYu, OU=Home, O=DFY, L=Mianyang, ST=Sichuan, C=CN" 2>/dev/null
fi
"$JAVA_HOME/bin/java.exe" -jar "$BT/lib/apksigner.jar" sign --ks dafeiyu.keystore \
  --ks-pass pass:"$KS_PASS" --key-pass pass:"$KS_PASS" --out app.apk app-unsigned.apk
"$JAVA_HOME/bin/java.exe" -jar "$BT/lib/apksigner.jar" verify --print-certs app.apk | head -3
ls -l app.apk
