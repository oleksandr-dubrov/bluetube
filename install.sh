#!/bin/bash


# The script installs all needed files of Bluetube
# to the specified directory.


if [ -z "$1" ]
  then
    echo "ERROR. Specify a directory."
    exit -1
fi


if [ ! -d "$1" ]; then
   echo $1 does not exist!
   exit -1
fi


DIRECTORY=$1/bluetube
echo Installing Bluetube to $DIRECTORY ...

FILES=( \
bluetube.py \
bcolors.py \
bluetoothclient.py \
feeds.py \
dependencies.txt \
README.md \
)

if [ ! -d "$DIRECTORY" ]; then
  mkdir "$DIRECTORY"
fi

RUNNER1=$'#!/bin/bash\n# Runner script for bluetube.py\npython2 '
RUNNER2=$'/bluetube.py "$@"'
RUNNER=$RUNNER1$DIRECTORY$RUNNER2

echo "$RUNNER" > $DIRECTORY/bluetube
chmod u+x "$DIRECTORY/bluetube"

for (( i=0; i<${#FILES[@]}; i++)); do
    echo Coping ${FILES[${i}]}.
    cp -f ${FILES[${i}]} "$DIRECTORY"
done

echo "Setting access modes..."
chmod 774 $DIRECTORY/bluetube
chmod 400 $DIRECTORY/bluetube.py
chmod 400 $DIRECTORY/bcolors.py
chmod 400 $DIRECTORY/bluetoothclient.py
chmod 400 $DIRECTORY/feeds.py
chmod 400 $DIRECTORY/dependencies.txt
chmod 400 $DIRECTORY/README.md

rm -rf $DIRECTORY/*.pyc

echo Done
exit 0
