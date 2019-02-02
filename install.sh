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
bluetube.py \
bluetube.cfg \
bluetube.dat \
dependencies.txt \
README.md \
)

if [ ! -d "$DIRECTORY" ]; then
  mkdir "$DIRECTORY"
fi

RUNNER1=$'#!/bin/bash\n# Runner script for bluetube.py\npython2 '
RUNNER2=$'/bluetube.py $@'
RUNNER=$RUNNER1$DIRECTORY$RUNNER2

echo "$RUNNER" > $DIRECTORY/bluetube
chmod u+x "$DIRECTORY/bluetube"

for (( i=0; i<${#FILES[@]}; i++)); do
    echo Coping ${FILES[${i}]} ...
    cp ${FILES[${i}]} "$DIRECTORY"
done

echo Done
exit 0
