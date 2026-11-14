#!/bin/bash
# Usage: fit.sh /abs/path/one-pager.html
# Finds the largest print font size that keeps the page on ONE letter sheet,
# writes it into the file's @media print rule, exports one-pager.pdf next to it
# and a screen screenshot (one-pager.png).
set -e
F="$1"; DIR="$(cd "$(dirname "$F")" && pwd)"; B="$(basename "$F" .html)"
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
pages(){ python3 -I -c "import re,sys;print(len(re.findall(rb'/Type\s*/Page[^s]',open(sys.argv[1],'rb').read())))" "$DIR/$B.pdf"; }
for f in 11.0 10.6 10.3 10.0 9.7 9.4 9.1 8.8 8.5 8.2 7.9; do
  sed -i '' -E "s/(@media print\{body\{font-size:)[0-9.]+px/\1${f}px/" "$F"
  "$C" --headless=new --no-pdf-header-footer --print-to-pdf="$DIR/$B.pdf" "file://$F" 2>/dev/null
  n=$(pages); echo "print font ${f}px -> $n page(s)"
  [ "$n" = 1 ] && break
done
[ "$n" = 1 ] || echo "STILL OVER ONE PAGE: cut content, do not shrink further."
"$C" --headless=new --hide-scrollbars --window-size=1200,1700 --virtual-time-budget=4000 --screenshot="$DIR/$B.png" "file://$F" 2>/dev/null
echo "PDF: $DIR/$B.pdf  screenshot: $DIR/$B.png"
