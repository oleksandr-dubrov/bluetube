#!/bin/bash

# The script installs all needed files of Bluetube
# to the specified directory.

if [ -z "$1" ]
  then
    echo "ERROR. Specify a directory."
    exit -1
fi

DIRECTORY=$1/bluetube
echo Installing Bluetube to $DIRECTORY ...

FILES=( \
bluetube.py \
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
    echo Coping ${FILES[${i}]}.
    cp ${FILES[${i}]} "$DIRECTORY"
done

echo "Setting access modes..."
chmod 771 $DIRECTORY/bluetube
chmod 400 $DIRECTORY/bluetube.py
chmod 400 $DIRECTORY/dependencies.txt
chmod 400 $DIRECTORY/README.md

echo Done
exit 0
