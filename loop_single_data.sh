#/bin/bin -l

if [ -z "$1" ]; then
    echo "Find raw .h5 files in the current directory: $(pwd)"
    DIR = "fastMRI_breast_001_1"
else
    echo "Find raw .h5 files in: $1"
    DIR="$1"
fi

FILES=$(find "$DIR" -maxdepth 1 -name "*.h5")
if [ -z "$FILES" ]; then
    echo "No .h5 files found in $DIR"
    exit 1
fi

FIRST_FILE=$(echo "$FILES" | head -n 1)
DATA="$FIRST_FILE"
DATA=$(basename "$FIRST_FILE")

if [ -z "$2" ]; then
    echo "> SPOKES set as default: 72"
    SPOKES=72
else
    NUM='^[0-9]+$'

    if [[ $2 =~ $NUM ]]; then
        SPOKES="$2"
    else
        echo "> Input $2 is not a number. SPOKES set as default: 72"
        SPOKES=72
    fi
fi

if [ -z "$3" ]; then
    echo "> SLICE_IDX set as default: 0"
    SLICE_IDX=0
else
    NUM='^[0-9]+$'

    if [[ $3 =~ $NUM ]]; then
        SLICE_IDX="$3"
    else
        echo "> Input $3 is not a number. SLICE_IDX set as default: 0"
        SLICE_IDX=0
    fi
fi

if [ -z "$4" ]; then
    echo "> SLICE_INC set as default: 192"
    SLICE_INC=192
else
    NUM='^[0-9]+$'

    if [[ $4 =~ $NUM ]]; then
        SLICE_INC="$4"
    else
        echo "> Input $2 is not a number. SLICE_INC set as default: 192"
        SLICE_INC=192
    fi
fi

    echo "> DIR: ${DIR}"
    echo "> DATA: ${DATA}"
    echo "> SPOKES: ${SPOKES}"
    echo "> SLICE_IDX: ${SLICE_IDX}"
    echo "> SLICE_INC: ${SLICE_INC}"

    # Check if SLICE_IDX is equal to zero
    if [ "$SLICE_IDX" -ne 0 ]; then  
        ((SLICE_IDX--))
        #echo "SLICE_IDX is now $SLICE_IDX"
    fi 
    # reconstruct slice by slice
    python dce_recon.py --dir ${DIR} --data ${DATA} --spokes_per_frame ${SPOKES} --slice_idx ${SLICE_IDX} --slice_inc ${SLICE_INC}

    # convert the .h5 file to dicom

    python dcm_recon.py --dir ${DIR} --h5py ${DATA} --spokes_per_frame ${SPOKES}


