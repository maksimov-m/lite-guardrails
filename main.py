from detectors import NsfwDetector, PiiDetector, RelevantDetector

DETECTORS = [PiiDetector(), NsfwDetector(), RelevantDetector()]


if __name__ == "__main__":
    text = "Привет! Мой номер 89991330855 и email maks@gmail.com"
    for detector in DETECTORS:
        print(f"{detector.name:9}", detector.detect(text))
