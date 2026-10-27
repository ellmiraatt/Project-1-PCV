import math
import random
import sys
import os
import cv2
import pygame

try:
    import mediapipe as mp
except ImportError:
    mp = None

pygame.init()
WIDTH, HEIGHT, FPS = 1100, 760, 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("SHADOW ESCAPE")
clock = pygame.time.Clock()

BG = (9, 12, 32)
PANEL = (20, 25, 55)
WHITE = (240, 245, 255)
CYAN = (40, 220, 255)
BLUE = (50, 90, 255)
PURPLE = (155, 65, 255)
GREEN = (60, 255, 155)
RED = (255, 70, 110)
GRAY = (150, 160, 190)
WALL = (45, 61, 120)
FLOOR = (17, 22, 48)

TITLE = pygame.font.SysFont("arial", 48, bold=True)
SUBTITLE = pygame.font.SysFont("arial", 20)
BUTTON_FONT = pygame.font.SysFont("arial", 23, bold=True)
TEXT = pygame.font.SysFont("arial", 17)
SMALL = pygame.font.SysFont("arial", 14)

COLS, ROWS, CELL = 21, 15, 32
MAZE_X, MAZE_Y = 38, 170
PLAYER_RADIUS, PLAYER_SPEED = 10, 175
CAM_W, CAM_H, DEADZONE = 640, 480, 0.22

MENU, HOW_TO, PLAYING, WIN = "menu", "how_to", "playing", "win"
state = MENU
DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1),
              "LEFT": (-1, 0), "RIGHT": (1, 0)}
locked_direction = (0, 0)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    menu_bg = pygame.image.load(os.path.join(BASE_DIR, "menu_bg.png")).convert()
    menu_bg = pygame.transform.smoothscale(menu_bg, (WIDTH, HEIGHT))
except (pygame.error, FileNotFoundError) as exc:
    print("Background menu tidak ditemukan:", exc)
    menu_bg = None


def text(s, font, color, x, y, center=True):
    image = font.render(s, True, color)
    rect = image.get_rect()
    rect.center = (x, y) if center else rect.topleft
    if not center:
        rect.topleft = (x, y)
    screen.blit(image, rect)
    return rect


def background():
    screen.fill(BG)
    for x in range(25, WIDTH, 55):
        for y in range(25, HEIGHT, 55):
            pygame.draw.circle(screen, (25, 33, 67), (x, y), 1)


def button(label, rect, mouse, color=BLUE):
    hover = rect.collidepoint(mouse)
    pygame.draw.rect(screen, PANEL, rect, border_radius=12)
    pygame.draw.rect(screen, CYAN if hover else color, rect, 2, border_radius=12)
    text(label, BUTTON_FONT, WHITE, rect.centerx, rect.centery)


def menu_rects():
    # Click areas aligned to the three buttons in menu_bg.png.
    return (pygame.Rect(365, 365, 370, 65),
            pygame.Rect(365, 460, 370, 65),
            pygame.Rect(365, 540, 370, 65))


def draw_menu(mouse):
    if menu_bg is not None:
        screen.blit(menu_bg, (0, 0))
    else:
        background()
        text("SHADOW", TITLE, CYAN, WIDTH // 2, 150)
        text("ESCAPE", TITLE, PURPLE, WIDTH // 2, 205)
        text("MOVE WITH YOUR HAND • ESCAPE THE MAZE",
             SUBTITLE, WHITE, WIDTH // 2, 255)
        p, h, q = menu_rects()
        button("PLAY GAME", p, mouse, BLUE)
        button("HOW TO PLAY", h, mouse, PURPLE)
        button("QUIT GAME", q, mouse, RED)
    p, h, q = menu_rects()
    # Subtle hover tint over the artwork buttons.
    for rect, color in ((p, CYAN), (h, PURPLE), (q, (230, 50, 220))):
        if rect.collidepoint(mouse) and menu_bg is not None:
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(overlay, (*color, 35), overlay.get_rect(), border_radius=12)
            screen.blit(overlay, rect.topleft)
            pygame.draw.rect(screen, color, rect, 2, border_radius=12)
    return p, h, q


def make_maze():
    data = [[1] * COLS for _ in range(ROWS)]
    data[1][1] = 0
    stack = [(1, 1)]
    steps = [(0, -2), (0, 2), (-2, 0), (2, 0)]
    while stack:
        x, y = stack[-1]
        choices = []
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1 and data[ny][nx]:
                choices.append((nx, ny, dx, dy))
        if choices:
            nx, ny, dx, dy = random.choice(choices)
            data[y + dy // 2][x + dx // 2] = 0
            data[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    data[ROWS - 2][COLS - 2] = 0
    return data


maze = make_maze()
player_x, player_y = MAZE_X + CELL * 1.5, MAZE_Y + CELL * 1.5


def new_game():
    global maze, player_x, player_y, locked_direction, state
    maze = make_maze()
    player_x, player_y = MAZE_X + CELL * 1.5, MAZE_Y + CELL * 1.5
    locked_direction = (0, 0)
    state = PLAYING


def draw_maze():
    for r in range(ROWS):
        for c in range(COLS):
            rect = pygame.Rect(MAZE_X + c * CELL, MAZE_Y + r * CELL, CELL, CELL)
            pygame.draw.rect(screen, WALL if maze[r][c] else FLOOR, rect)
            if maze[r][c]:
                pygame.draw.rect(screen, (33, 46, 92), rect, 1)
    start = pygame.Rect(MAZE_X + CELL, MAZE_Y + CELL, CELL, CELL)
    pygame.draw.rect(screen, (25, 85, 82), start)
    ex = MAZE_X + (COLS - 2) * CELL
    ey = MAZE_Y + (ROWS - 2) * CELL
    exit_rect = pygame.Rect(ex + 3, ey + 3, CELL - 6, CELL - 6)
    pygame.draw.rect(screen, GREEN, exit_rect, border_radius=7)
    text("EXIT", SMALL, (8, 30, 25), exit_rect.centerx, exit_rect.centery)


def wall_collision(x, y):
    left = math.floor((x - PLAYER_RADIUS - MAZE_X) / CELL)
    right = math.floor((x + PLAYER_RADIUS - MAZE_X) / CELL)
    top = math.floor((y - PLAYER_RADIUS - MAZE_Y) / CELL)
    bottom = math.floor((y + PLAYER_RADIUS - MAZE_Y) / CELL)
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            if r < 0 or r >= ROWS or c < 0 or c >= COLS:
                return True
            if maze[r][c]:
                wall = pygame.Rect(MAZE_X + c * CELL, MAZE_Y + r * CELL, CELL, CELL)
                player = pygame.Rect(round(x - PLAYER_RADIUS), round(y - PLAYER_RADIUS),
                                     PLAYER_RADIUS * 2, PLAYER_RADIUS * 2)
                if player.colliderect(wall):
                    return True
    return False


def move_player(dt):
    global player_x, player_y, state
    dx, dy = locked_direction
    length = math.hypot(dx, dy)
    if length:
        dx, dy = dx / length, dy / length
    nx, ny = player_x + dx * PLAYER_SPEED * dt, player_y + dy * PLAYER_SPEED * dt
    if not wall_collision(nx, player_y):
        player_x = nx
    if not wall_collision(player_x, ny):
        player_y = ny
    exit_x = MAZE_X + (COLS - 1.5) * CELL
    exit_y = MAZE_Y + (ROWS - 1.5) * CELL
    if abs(player_x - exit_x) < CELL * .45 and abs(player_y - exit_y) < CELL * .45:
        state = WIN


def draw_player():
    pos = (round(player_x), round(player_y))
    pygame.draw.circle(screen, (18, 88, 140), pos, PLAYER_RADIUS + 5)
    pygame.draw.circle(screen, CYAN, pos, PLAYER_RADIUS)
    pygame.draw.circle(screen, WHITE, (pos[0] - 3, pos[1] - 3), 3)


cap = None
hands = None
mp_draw = None


def init_camera():
    global cap, hands, mp_draw
    if mp is None:
        print("MediaPipe belum terpasang; gunakan keyboard.")
        return
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Webcam tidak tersedia; gunakan keyboard.")
            cap.release()
            cap = None
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
        hands = mp.solutions.hands.Hands(
            static_image_mode=False, max_num_hands=1, model_complexity=0,
            min_detection_confidence=.6, min_tracking_confidence=.6)
        mp_draw = mp.solutions.drawing_utils
        print("Webcam dan MediaPipe siap.")
    except Exception as exc:
        print("Gagal menyiapkan webcam:", exc)
        if cap:
            cap.release()
        cap = None
        hands = None


def read_hand():
    if cap is None or hands is None:
        return None, None
    ok, frame = cap.read()
    if not ok:
        return None, None
    frame = cv2.flip(frame, 1)
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    position = None
    if result.multi_hand_landmarks:
        lm = result.multi_hand_landmarks[0]
        palm = lm.landmark[9]
        position = (max(0, min(1, palm.x)), max(0, min(1, palm.y)))
        mp_draw.draw_landmarks(frame, lm, mp.solutions.hands.HAND_CONNECTIONS)
    return frame, position


def sensor_direction(position):
    # None means keep the existing direction lock.
    if position is None:
        return None
    dx, dy = position[0] - .5, position[1] - .5
    if abs(dx) < DEADZONE and abs(dy) < DEADZONE:
        return None
    if abs(dx) > abs(dy):
        return DIRECTIONS["LEFT"] if dx < 0 else DIRECTIONS["RIGHT"]
    return DIRECTIONS["UP"] if dy < 0 else DIRECTIONS["DOWN"]


def draw_camera(frame, position):
    x, y, w, h = 755, 190, 315, 236
    outer = pygame.Rect(x - 6, y - 6, w + 12, h + 12)
    pygame.draw.rect(screen, PANEL, outer, border_radius=10)
    pygame.draw.rect(screen, CYAN, outer, 2, border_radius=10)
    if frame is None:
        pygame.draw.rect(screen, (13, 18, 40), (x, y, w, h), border_radius=6)
        text("WEBCAM UNAVAILABLE", TEXT, RED, x + w // 2, y + h // 2 - 10)
        text("Use keyboard controls", SMALL, GRAY, x + w // 2, y + h // 2 + 16)
        return
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (w, h))
    surface = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
    screen.blit(surface, (x, y))
    cx, cy = x + w // 2, y + h // 2
    zw, zh = int(w * DEADZONE), int(h * DEADZONE)
    zone = pygame.Rect(cx - zw, cy - zh, zw * 2, zh * 2)
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (60, 255, 155, 60),
                     (zone.x - x, zone.y - y, zone.width, zone.height), border_radius=6)
    screen.blit(overlay, (x, y))
    pygame.draw.rect(screen, GREEN, zone, 2)
    if position:
        pygame.draw.circle(screen, RED,
                           (int(x + position[0] * w), int(y + position[1] * h)), 7)


def draw_how_to(mouse):
    background()
    text("HOW TO PLAY", TITLE, CYAN, WIDTH // 2, 120)
    lines = [
        "Move your hand away from the center of the webcam image.",
        "Hand LEFT / RIGHT / UP / DOWN selects a direction.",
        "Returning your hand to the center keeps the last direction.",
        "Move your hand to another zone to change direction.",
        "Walls block the player. Find the green EXIT tile.",
        "Keyboard alternative: WASD or Arrow Keys.",
        "Press ESC to return to the main menu."
    ]
    for i, line in enumerate(lines):
        text(line, TEXT, WHITE, WIDTH // 2, 245 + i * 42)
    back = pygame.Rect(410, 570, 280, 55)
    button("BACK TO MENU", back, mouse, PURPLE)
    return back


def draw_game(frame, position):
    background()
    text("SHADOW ESCAPE", TITLE, CYAN, WIDTH // 2, 65)
    text("Navigate the maze and reach the EXIT", SUBTITLE, GRAY, WIDTH // 2, 112)
    draw_maze()
    draw_player()
    text("HAND SENSOR", BUTTON_FONT, WHITE, 910, 145)
    draw_camera(frame, position)
    direction_name = next((name for name, value in DIRECTIONS.items()
                           if value == locked_direction), "STOP / NONE")
    text("LOCKED DIRECTION", TEXT, GRAY, 910, 465)
    text(direction_name, BUTTON_FONT,
         GREEN if locked_direction != (0, 0) else GRAY, 910, 495)
    text("Move hand to change direction", SMALL, WHITE, 910, 535)
    text("WASD / Arrow Keys: Move", SMALL, GRAY, 910, 590)
    text("ESC: Main Menu", SMALL, GRAY, 910, 615)
    text("Center keeps last direction", SMALL, GREEN, 910, 650)


def draw_win(mouse):
    background()
    text("YOU ESCAPED!", TITLE, GREEN, WIDTH // 2, 240)
    text("You found your way out of the maze.", SUBTITLE, WHITE, WIDTH // 2, 300)
    replay = pygame.Rect(390, 390, 320, 58)
    main_menu = pygame.Rect(390, 470, 320, 58)
    button("PLAY AGAIN", replay, mouse, BLUE)
    button("MAIN MENU", main_menu, mouse, PURPLE)
    return replay, main_menu


init_camera()
running = True
while running:
    dt = min(clock.tick(FPS) / 1000.0, .05)
    mouse = pygame.mouse.get_pos()
    frame = position = None

    if state == PLAYING:
        frame, position = read_hand()
        detected = sensor_direction(position)
        if detected is not None:
            locked_direction = detected

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if state in (PLAYING, HOW_TO):
                    state = MENU
                    locked_direction = (0, 0)
                elif state == WIN:
                    state = MENU
            if state == PLAYING:
                if event.key in (pygame.K_UP, pygame.K_w):
                    locked_direction = DIRECTIONS["UP"]
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    locked_direction = DIRECTIONS["DOWN"]
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    locked_direction = DIRECTIONS["LEFT"]
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    locked_direction = DIRECTIONS["RIGHT"]

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if state == MENU:
                play, how, quit_rect = menu_rects()
                if play.collidepoint(event.pos):
                    new_game()
                elif how.collidepoint(event.pos):
                    state = HOW_TO
                elif quit_rect.collidepoint(event.pos):
                    running = False
            elif state == HOW_TO:
                if pygame.Rect(410, 570, 280, 55).collidepoint(event.pos):
                    state = MENU
            elif state == WIN:
                replay = pygame.Rect(390, 390, 320, 58)
                main_menu = pygame.Rect(390, 470, 320, 58)
                if replay.collidepoint(event.pos):
                    new_game()
                elif main_menu.collidepoint(event.pos):
                    state = MENU

    if state == PLAYING:
        move_player(dt)

    if state == MENU:
        draw_menu(mouse)
    elif state == HOW_TO:
        draw_how_to(mouse)
    elif state == PLAYING:
        draw_game(frame, position)
    elif state == WIN:
        draw_win(mouse)

    pygame.display.flip()

if cap is not None:
    cap.release()
if hands is not None:
    hands.close()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()
