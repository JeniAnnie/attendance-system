import pickle

try:
    import face_recognition
    FACE_RECOG_AVAILABLE = True
except ImportError:
    face_recognition = None
    FACE_RECOG_AVAILABLE = False

ENCODINGS_FILE = "face_data.pkl"

def recognize_face(frame):

    if not FACE_RECOG_AVAILABLE:
        return None

    try:
        data = pickle.load(open(ENCODINGS_FILE, "rb"))
    except Exception:
        return None

    known_encodings = data.get("encodings", [])
    known_ids = data.get("ids", [])

    face_locations = face_recognition.face_locations(frame)
    face_encodings = face_recognition.face_encodings(frame, face_locations)

    for encoding in face_encodings:

        matches = face_recognition.compare_faces(
            known_encodings, encoding
        )

        if True in matches:

            index = matches.index(True)
            return known_ids[index]

    return None