from collections import defaultdict
import os
import pickle

import cv2
import np

ORB_IMG_SIZE = 40

class PadVision:
    def __init__(self, bot):
        self.bot = bot

def setup(bot):
    n = PadVision(bot)
    bot.add_cog(n)


###############################################################################
# Library code
###############################################################################

EXTRACTABLE = 'rbgldhjpmo'

# returns y, x
def board_iterator():
    for y in range(5):
        for x in range(6):
            yield y, x


def dbg_display(img):
    cv2.namedWindow('image', cv2.WINDOW_NORMAL)
    cv2.imshow('image', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Compare two images by getting the L2 error (square-root of sum of squared error).
def getL2Err(A, B):
    # Calculate the L2 relative error between images.
    errorL2 = cv2.norm(A, B, cv2.NORM_L2);
    # Convert to a reasonable scale, since L2 error is summed across all pixels of the image.
    return errorL2 / (100 * 100);

# Compare two images by getting the L2 error (square-root of sum of squared error).
def getL2ErrThresholded(A, B):
    A = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY)
    B = cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)
    A = cv2.adaptiveThreshold(A, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 7, 3)
    B = cv2.adaptiveThreshold(B, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 7, 3)

    # Calculate the L2 relative error between images.
    errorL2 = cv2.norm(A, B, cv2.NORM_L2);
    # Convert to a reasonable scale, since L2 error is summed across all pixels of the image.
    return errorL2 / (100 * 100);

def getMSErr(imageA, imageB):
    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    # NOTE: the two images must have the same dimension
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])

    # return the MSE, the lower the error, the more "similar"
    # the two images are
    return err

def getMSErrThresholded(imageA, imageB):
    imageA = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY)
    imageB = cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
    imageA = cv2.adaptiveThreshold(imageA, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 7, 2)
    imageB = cv2.adaptiveThreshold(imageB, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 7, 2)

    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    # NOTE: the two images must have the same dimension
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])

    # return the MSE, the lower the error, the more "similar"
    # the two images are
    return err

def resizeOrbImg(img):
    height, width, _ = img.shape
    if height < ORB_IMG_SIZE or width < ORB_IMG_SIZE:
        return cv2.resize(img, (ORB_IMG_SIZE, ORB_IMG_SIZE), interpolation=cv2.INTER_CUBIC)
    elif height > ORB_IMG_SIZE or width > ORB_IMG_SIZE:
        return cv2.resize(img, (ORB_IMG_SIZE, ORB_IMG_SIZE), interpolation=cv2.INTER_AREA)
    else:
        return img

def find_best_match(orb_img, orb_type_to_images, similarity_fn):
    best_match = 'u'
    best_match_sim = 99999
    for orb_type, image_list in orb_type_to_images.items():
        for i in image_list:
            sim = similarity_fn(orb_img, i)
            if sim < best_match_sim:
                best_match = orb_type
                best_match_sim = sim
    return best_match, best_match_sim

def load_orb_images_dir_to_map(orb_image_dir):
    orb_type_to_images = defaultdict(list)

    for f in os.listdir(orb_image_dir):
        img = cv2.imread('{}/{}'.format(orb_image_dir, f), cv2.IMREAD_COLOR)
        img = resizeOrbImg(img)
        orb_type = f[0]
        orb_type_to_images[orb_type].append(img)

    return orb_type_to_images

def load_hsv_to_orb(hsv_file_path):
    try:
        return pickle.load(open(hsv_file_path, 'rb'))
    except Exception as ex:
        print('failed to load hsv pixel to orb map', ex)
    return {}


class OrbExtractor(object):
    def __init__(self, img):
        self.img = img
        self.find_start_end()
        self.compute_sizes()

    def find_start_end(self):
        img = self.img
        height, width, _ = img.shape

        # Detect left/right border size
        xstart = 0
        while True:
            low = int(height * 2 / 3)
            # board starts in the lower half, and has slightly deeper indentation
            # than the monster display
            if max(img[low, xstart]) > 0:
                break
            xstart += 1

        # compute true baseline from the bottom (removes android buttons)
        yend = height - 1
        while True:
            if max(img[yend, xstart + 10]) > 0:
                break
            yend -= 1

        self.xstart = xstart
        self.yend = yend

        self.x_adj = 0
        self.y_adj = 2
        self.orb_adj = 1

    def compute_sizes(self):
        img = self.img
        height, width, _ = img.shape

        # compute true board size
        board_width = width - (self.xstart * 2) - self.x_adj
        orb_size = board_width / 6 - self.orb_adj

        ystart = self.yend - orb_size * 5 + self.y_adj

        self.ystart = ystart
        self.orb_size = orb_size

    def get_orb_vertices(self, x, y):
        # Consider adding an offset here to get rid of padding?
        offset = 0
        box_ystart = y * self.orb_size + self.ystart
        box_yend = box_ystart + self.orb_size
        box_xstart = x * self.orb_size + self.xstart
        box_xend = box_xstart + self.orb_size
        return int(box_xstart + offset), int(box_ystart + offset), int(box_xend - offset), int(box_yend - offset)

    def get_orb_coords(self, x, y):
        box_xstart, box_ystart, box_xend, box_yend = self.get_orb_vertices(x, y)
        coords = (slice(box_ystart, box_yend),
                slice(box_xstart, box_xend),
                slice(None))
        return coords

    def get_orb_img(self, x, y):
        return self.img[self.get_orb_coords(x, y)]


class SimilarityBoardExtractor(object):
    def __init__(self, orb_type_to_images, img):
        self.orb_type_to_images = orb_type_to_images
        self.img = img
        self.processed = False
        self.results = [['u' for x in range(6)] for y in range(5)]
        self.similarity = [[0 for x in range(6)] for y in range(5)]

    def process(self):
        oe = OrbExtractor(self.img)

        for y, x in board_iterator():
            orb_img = oe.get_orb_img(x, y)
            orb_img = resizeOrbImg(orb_img)

            best_match, best_match_sim = find_best_match(orb_img, self.orb_type_to_images, getL2ErrThresholded)
            self.results[y][x] = best_match
            self.similarity[y][x] = best_match_sim

    def get_board(self):
        if not self.processed:
            self.process()
            self.processed = True
        return self.results

    def get_similarity(self):
        return self.similarity


def pixel_array_to_tuple(pixel):
    # Converts an HSV pixel into a tuple used as a key
    # don't need to store V, H/S is good enough
    return (pixel[0], pixel[1])

class PixelCompareBoardExtractor(object):
    def __init__(self, hsv_pixels_to_orb, hsv_img):
        self.hsv_pixels_to_orb = hsv_pixels_to_orb
        self.hsv_img = hsv_img
        self.processed = False
        self.results = [['u' for x in range(6)] for y in range(5)]

    def process(self):
        oe = OrbExtractor(self.hsv_img)

        for y, x in board_iterator():
            orb_img = oe.get_orb_img(x, y)

            detected_orb = self.process_orb(orb_img)
            if detected_orb:
                self.results[y][x] = detected_orb

        self.processed = True

    def process_orb(self, orb_img):
        height, width, _ = orb_img.shape
        for y in range(height):
            for x in range(width):
                pixel = orb_img[y][x]
                key = pixel_array_to_tuple(pixel)
                matched_orb = self.hsv_pixels_to_orb.get(key, None)
                if matched_orb is not None:
                    return matched_orb
        return None

    def get_board(self):
        if not self.processed:
            self.process()

        return self.results
