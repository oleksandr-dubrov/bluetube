#!/bin/bash

# The script installs all needed files of Bluetube
# to the specified directory.

if [ -z "$1" ]
  then
    echo "ERROR. Specify a directory."
    exit -1
fi

DIRECTORY=$1/bluetube
echo Installing Bluetube to $DIRECTORY

FILES=( \
bluetube \
bluetube.py \
bluetube.cfg \
bluetube.dat \
dependencies.txt \
README.md \
)

if [ ! -d "$DIRECTORY" ]; then
  mkdir "$DIRECTORY"
fi

for (( i=0; i<${#FILES[@]}; i++)); do
    echo Coping ${FILES[${i}]} ...
    cp ${FILES[${i}]} "$DIRECTORY"
done

echo Done
exit 0
