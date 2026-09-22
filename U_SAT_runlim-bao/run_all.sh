#!/bin/bash

# Tạo thư mục chứa log kiểm soát tài nguyên của runlim
mkdir -p runlim_logs

# Danh sách bài test: "NAME M C"
INSTANCES=(
"MERTENS 6 6"
"MERTENS 2 18"
"BOWMAN 5 20"
"JAESCHKE 8 6"
"JAESCHKE 3 18"
"JACKSON 8 7"
"JACKSON 3 21"
"MANSOOR 4 48"
"MANSOOR 2 94"
"MITCHELL 8 14"
"MITCHELL 3 39"
"ROSZIEG 10 14"
"ROSZIEG 4 32"
"BUXEY 7 47"
"BUXEY 14 25"
"SAWYER 14 25"
"SAWYER 7 47"
)

for inst in "${INSTANCES[@]}"; do
    # Tách tham số
    read -r NAME M C <<< "$inst"
    LOG_FILE="runlim_logs/${NAME}_${M}_${C}.log"

    echo "=================================================="
    echo "Running: $NAME (Machines=$M, Cycle=$C) | Timeout: 3600s"
    echo "=================================================="

    # Gọi runlim bọc ngoài lệnh python
    # -t 3600: Giới hạn 3600 giây CPU
    # -s 4096: Giới hạn 4GB RAM
    # -o: Lưu log tài nguyên của runlim vào thư mục runlim_logs/
    runlim -t 3600 -s 4096 -o "$LOG_FILE" python3 solve_single.py "$NAME" "$M" "$C"

    EXIT_STATUS=$?
    if [ $EXIT_STATUS -ne 0 ]; then
        echo "--> [TIMEOUT / STOPPED] Test $NAME bị ngắt do vượt giới hạn. Đã lưu kết quả tốt nhất trước đó vào results.csv!"
    fi
done