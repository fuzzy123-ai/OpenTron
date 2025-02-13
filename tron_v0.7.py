import pygame
import random
import math
import time
import os

# Initialisierung
pygame.init()

# Farben
WHITE     = (255, 255, 255)
BLACK     = (0, 0, 0)
RED       = (255, 100, 100)
GREEN     = (100, 255, 100)
LIGHT_BLUE= (100, 100, 255)
YELLOW    = (255, 255, 100)
MAGENTA   = (255, 100, 255)
CYAN      = (100, 255, 255)
GRAY      = (50, 50, 50)
DARK_GRAY = (30, 30, 30)

COLORS = [GREEN, RED, LIGHT_BLUE, YELLOW, MAGENTA, CYAN]

# Display-Einstellungen
info = pygame.display.Info()
DESKTOP_W, DESKTOP_H = info.current_w, info.current_h
BLOCK_SIZE = 20
MIN_DISTANCE = 200
GAME_DURATION = 15 * 60

# Schriftarten
font = pygame.font.SysFont("Arial", 30)
large_font = pygame.font.SysFont("Arial", 50)
# Für Buttons verwenden wir eine Schrift, die ca. 20% kleiner ist
button_font = pygame.font.SysFont("Arial", int(50 * 0.8))

# Uhr für die Spielgeschwindigkeit
clock = pygame.time.Clock()

pygame.mixer.init()

# --- Button-Klasse (für diskrete Einstellungen) ---
class Button:
    def __init__(self, rect, normal_bg, normal_text_color, blink_bg, blink_text_color, text, callback, blink_duration=0.2):
        self.rect = pygame.Rect(rect)
        self.normal_bg = normal_bg
        self.normal_text_color = normal_text_color
        self.blink_bg = blink_bg
        self.blink_text_color = blink_text_color
        self.text = text
        self.callback = callback
        self.blink_duration = blink_duration
        self.is_blinking = False
        self.blink_start_time = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.is_blinking = True
                self.blink_start_time = time.time()
                if self.callback:
                    self.callback()

    def update(self):
        if self.is_blinking and (time.time() - self.blink_start_time > self.blink_duration):
            self.is_blinking = False

    def draw(self, surface, font):
        bg = self.blink_bg if self.is_blinking else self.normal_bg
        text_color = self.blink_text_color if self.is_blinking else self.normal_text_color
        pygame.draw.rect(surface, bg, self.rect)
        pygame.draw.rect(surface, WHITE, self.rect, 3)  # Weiße Umrandung
        text_surf = font.render(self.text, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


# --- Slider-Klasse (für kontinuierliche Einstellungen, z. B. Zoom) ---
class Slider:
    def __init__(self, rect, min_value, max_value, initial_value, track_color, knob_color):
        self.rect = pygame.Rect(rect)  # Der Schienenbereich
        self.min_value = min_value
        self.max_value = max_value
        self.value = initial_value
        self.track_color = track_color
        self.knob_color = knob_color
        self.knob_radius = self.rect.height // 2
        self.dragging = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.get_knob_rect().collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            rel_x = max(0, min(self.rect.width, rel_x))
            fraction = rel_x / self.rect.width
            self.value = self.min_value + fraction * (self.max_value - self.min_value)

    def get_knob_rect(self):
        fraction = (self.value - self.min_value) / (self.max_value - self.min_value)
        knob_x = self.rect.x + fraction * self.rect.width
        knob_rect = pygame.Rect(0, 0, self.knob_radius * 2, self.knob_radius * 2)
        knob_rect.center = (int(knob_x), self.rect.centery)
        return knob_rect

    def draw(self, surface):
        pygame.draw.rect(surface, self.track_color, self.rect)
        knob_rect = self.get_knob_rect()
        pygame.draw.ellipse(surface, self.knob_color, knob_rect)
        pygame.draw.ellipse(surface, WHITE, knob_rect, 2)


# --- Player-Klasse ---
class Player:
    def __init__(self, control_type, color, start_pos, direction, gap_chance=0.1, min_gap=2, max_gap=4):
        # Kopf und statische Spur (Trail) werden getrennt geführt
        self.head = start_pos.copy()
        self.trail = [start_pos.copy()]
        self.dx, self.dy = direction
        self.controller = None
        self.control_type = control_type
        self.color = color
        self.alive = True
        self.confirmed = False
        self.circle_size = BLOCK_SIZE // 2  # Basisgröße (z.B. für den Kopf)
        self.angle = 0
        self.turn_speed = 0.2
        self.turn_left = False
        self.turn_right = False
        self.trail_counter = 0
        self.highlighted = False
        self.highlight_start_time = 0

        # Parameter für zufällige Lücken:
        self.gap_chance = gap_chance    # z.B. 10 % Chance pro Update, ein Gap zu starten
        self.min_gap = min_gap          # Mindestlänge in Updates (z.B. 2)
        self.max_gap = max_gap          # Maximallänge in Updates (z.B. 4)
        self.current_gap_remaining = 0  # Zähler, wie viele Updates noch keine Spur erzeugt werden
        # Optional: Kopfbild (wenn du später den Kopf durch ein PNG ersetzen möchtest)
        self.head_image = None

    def update_position(self, world_width, world_height):
        if not self.alive:
            return

        self.trail_counter += 1

        # Wenn ein Gap aktiv ist, verringere den Zähler und füge kein Segment hinzu.
        if self.current_gap_remaining > 0:
            self.current_gap_remaining -= 1
        else:
            # Mit einer gewissen Wahrscheinlichkeit ein Gap starten:
            if random.random() < self.gap_chance:
                # Wähle eine zufällige Gap-Länge zwischen min_gap und max_gap.
                self.current_gap_remaining = random.randint(self.min_gap, self.max_gap)
            else:
                # Füge den aktuellen Kopf (als Kopie) zur statischen Spur hinzu.
                self.trail.append(self.head.copy())

        # Aktualisiere die Kopfposition:
        new_head = [self.head[0] + self.dx, self.head[1] + self.dy]
        if new_head[0] >= world_width:
            new_head[0] = 0
        elif new_head[0] < 0:
            new_head[0] = world_width - BLOCK_SIZE
        if new_head[1] >= world_height:
            new_head[1] = 0
        elif new_head[1] < 0:
            new_head[1] = world_height - BLOCK_SIZE
        self.head = new_head


    def check_collision(self, players, zoom):
        if not self.alive:
            return
        head = self.head
        collision_radius = (self.circle_size * zoom) * 0.8
        for segment in self.trail:
            if math.dist(head, segment) < collision_radius:
                self.alive = False
        for p in players:
            if p != self and p.alive:
                for segment in p.trail:
                    if math.dist(head, segment) < collision_radius:
                        self.alive = False


def generate_start_positions(num_players, width, height):
    positions = []
    directions = []
    regions = [
        (width // 4, height // 4),
        (3 * width // 4, height // 4),
        (width // 4, 3 * height // 4),
        (3 * width // 4, 3 * height // 4)
    ]
    dir_options = [(BLOCK_SIZE, 0), (-BLOCK_SIZE, 0), (0, BLOCK_SIZE), (0, -BLOCK_SIZE)]
    for i in range(num_players):
        pos = list(regions[i % 4])
        d = random.choice(dir_options)
        if i >= 4:
            pos[0] += random.randint(-100, 100)
            pos[1] += random.randint(-100, 100)
        while any(math.dist(pos, p) < MIN_DISTANCE for p in positions):
            pos[0] = random.randint(BLOCK_SIZE, width - BLOCK_SIZE)
            pos[1] = random.randint(BLOCK_SIZE, height - BLOCK_SIZE)
        positions.append(pos)
        directions.append(d)
    return positions, directions

def load_image(filename, scale=None):
    """
    Lädt ein Bild aus dem Unterordner 'assets'.
    
    :param filename: Name der Bilddatei (z. B. "tron.png").
    :param scale: Optionales Tuple (Breite, Höhe) zum Skalieren des Bildes.
    :return: Das geladene (und ggf. skalierte) Bild oder None, falls ein Fehler auftritt.
    """
    import os
    path = os.path.join("assets", filename)
    try:
        image = pygame.image.load(path).convert_alpha()
    except Exception as e:
        print(f"Fehler beim Laden von {path}: {e}")
        return None
    if scale is not None:
        image = pygame.transform.scale(image, scale)
    return image

def play_music(filename):
    """
    Lädt und spielt eine Musikdatei aus dem Unterordner 'assets' in Endlosschleife.
    """
    music_path = os.path.join("assets", filename)
    try:
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.play(-1)  # Endlos-Schleife
    except Exception as e:
        print(f"Fehler beim Laden der Musik '{music_path}': {e}")

def transition_music(new_music, fade_duration=3000):
    """
    Blendet das aktuell laufende Musikstück über 'fade_duration' Millisekunden aus
    und startet dann das neue Musikstück mit gleichem Fade‑in.
    :param new_music: Dateiname (z.B. "theme.mp3") im Unterordner "assets".
    :param fade_duration: Dauer des Fade‑out und Fade‑in in Millisekunden.
    """
    import os
    # Starte das Ausblenden der aktuellen Musik
    pygame.mixer.music.fadeout(fade_duration)
    # Warten, bis der Fade-Out abgeschlossen ist (diese Pause blockiert kurz den Thread)
    pygame.time.delay(fade_duration)
    
    # Lade und starte die neue Musik mit Fade-In
    new_music_path = os.path.join("assets", new_music)
    try:
        pygame.mixer.music.load(new_music_path)
        pygame.mixer.music.play(-1, fade_ms=fade_duration)
    except Exception as e:
        print(f"Fehler beim Laden der Musik '{new_music_path}': {e}")


# --- Startbildschirm (Menü) ---
def start_screen():
    screen = pygame.display.set_mode((DESKTOP_W, DESKTOP_H), pygame.FULLSCREEN)
    pygame.display.set_caption("Tron - Startmenü")
    play_music("music.mp3")
    title_image = load_image("tron.png", (DESKTOP_W /2, DESKTOP_H / 2))
    if title_image:
        title_rect = title_image.get_rect(center=(DESKTOP_W // 2, DESKTOP_H // 4))
    # Spieler erstellen
    players = []
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    players.append(Player("keyboard", COLORS[0], [0, 0], (0, 0)))
    for i, joy in enumerate(joysticks):
        joy.init()
        p = Player("controller", COLORS[i + 1], [0, 0], (0, 0))
        p.controller = joy
        players.append(p)
    
    positions, directions = generate_start_positions(len(players), DESKTOP_W, DESKTOP_H)
    for i, p in enumerate(players):
        p.trail = [[positions[i][0], positions[i][1]]]
        p.dx, p.dy = directions[i]
    
    # --- Diskrete Einstellungen ---
    # Geschwindigkeitsoptionen
    speed_options = [10, 15, 20, 25]
    speed_index = 1  # Startwert: 15
    speed = speed_options[speed_index]
    
    # Schlangenbreitenoptionen (als Wert für p.circle_size)
    snake_width_options = [8, 10, 12, 14]
    snake_width_index = 1  # Startwert: 10
    snake_width = snake_width_options[snake_width_index]
    
    # Drehgeschwindigkeitsoptionen (für p.turn_speed)
    turn_speed_options = [0.1, 0.2, 0.3, 0.4]
    turn_speed_index = 1  # Startwert: 0.2
    turn_speed = turn_speed_options[turn_speed_index]
    
    def update_speed(change):
        nonlocal speed_index, speed
        speed_index = max(0, min(speed_index + change, len(speed_options) - 1))
        speed = speed_options[speed_index]
    
    def update_snake_width(change):
        nonlocal snake_width_index, snake_width
        snake_width_index = max(0, min(snake_width_index + change, len(snake_width_options) - 1))
        snake_width = snake_width_options[snake_width_index]
    
    def update_turn_speed(change):
        nonlocal turn_speed_index, turn_speed
        turn_speed_index = max(0, min(turn_speed_index + change, len(turn_speed_options) - 1))
        turn_speed = turn_speed_options[turn_speed_index]
    
    # --- Buttons (ca. 20% kleiner: 48x48) ---
    button_size = 48
    # Für die Speed-Gruppe: Buttons weiter auseinander (hier ca. 200 Pixel links/rechts vom Zentrum)
    speed_button_y = DESKTOP_H // 2 + int(40 * 0.8)
    minus_speed_x = DESKTOP_W // 2 - int(200)   # statt 180*0.8 (144) jetzt ca. 200 Pixel
    plus_speed_x  = DESKTOP_W // 2 + int(200)     # symmetrisch
    minus_speed_button = Button(
        rect=(minus_speed_x, speed_button_y, button_size, button_size),
        normal_bg=BLACK,
        normal_text_color=WHITE,
        blink_bg=WHITE,
        blink_text_color=BLACK,
        text="-",
        callback=lambda: update_speed(-1)
    )
    plus_speed_button = Button(
        rect=(plus_speed_x, speed_button_y, button_size, button_size),
        normal_bg=WHITE,
        normal_text_color=BLACK,
        blink_bg=BLACK,
        blink_text_color=WHITE,
        text="+",
        callback=lambda: update_speed(1)
    )
    speed_button_list = [minus_speed_button, plus_speed_button]
    speed_text_center = (DESKTOP_W // 2, speed_button_y + button_size // 2)
    
    # Schlangenbreiten-Gruppe (etwas unterhalb)
    snake_button_y = speed_button_y + 80
    minus_snake_x = DESKTOP_W // 2 - int(200)
    plus_snake_x  = DESKTOP_W // 2 + int(200)
    minus_snake_button = Button(
        rect=(minus_snake_x, snake_button_y, button_size, button_size),
        normal_bg=BLACK,
        normal_text_color=WHITE,
        blink_bg=WHITE,
        blink_text_color=BLACK,
        text="-",
        callback=lambda: update_snake_width(-1)
    )
    plus_snake_button = Button(
        rect=(plus_snake_x, snake_button_y, button_size, button_size),
        normal_bg=WHITE,
        normal_text_color=BLACK,
        blink_bg=BLACK,
        blink_text_color=WHITE,
        text="+",
        callback=lambda: update_snake_width(1)
    )
    snake_button_list = [minus_snake_button, plus_snake_button]
    snake_text_center = (DESKTOP_W // 2, snake_button_y + button_size // 2)
    
    # Drehgeschwindigkeits-Gruppe (unterhalb der Schlangenbreiten-Gruppe)
    turn_speed_button_y = snake_button_y + 80
    minus_turn_x = DESKTOP_W // 2 - int(200)
    plus_turn_x  = DESKTOP_W // 2 + int(200)
    minus_turn_button = Button(
        rect=(minus_turn_x, turn_speed_button_y, button_size, button_size),
        normal_bg=BLACK,
        normal_text_color=WHITE,
        blink_bg=WHITE,
        blink_text_color=BLACK,
        text="-",
        callback=lambda: update_turn_speed(-1)
    )
    plus_turn_button = Button(
        rect=(plus_turn_x, turn_speed_button_y, button_size, button_size),
        normal_bg=WHITE,
        normal_text_color=BLACK,
        blink_bg=BLACK,
        blink_text_color=WHITE,
        text="+",
        callback=lambda: update_turn_speed(1)
    )
    turn_speed_button_list = [minus_turn_button, plus_turn_button]
    turn_speed_text_center = (DESKTOP_W // 2, turn_speed_button_y + button_size // 2)
    
    # --- Zoom-Slider ---
    zoom_slider_rect = (DESKTOP_W // 2 - 100, turn_speed_button_y + 80, 200, 20)
    zoom_slider = Slider(zoom_slider_rect, 0.5, 1.0, 1.0, track_color=GRAY, knob_color=WHITE)
    zoom_text_center = (DESKTOP_W // 2, zoom_slider_rect[1] - 20)
    
    # --- TRON-Titel oben (Sci-Fi-Schrift) ---
    # Lade eine Sci-Fi-Schriftart (z.B. "sci_fi.ttf" muss im Arbeitsverzeichnis liegen)
    try:
        sci_fi_font = pygame.font.Font("sci_fi.ttf", 100)
    except Exception:
        # Falls die Schrift nicht gefunden wird, verwende eine Standardschrift
        sci_fi_font = large_font
    tron_text = sci_fi_font.render("TRON", True, WHITE)
    tron_rect = tron_text.get_rect(center=(DESKTOP_W // 2, DESKTOP_H // 4))
    
    while True:
        screen.fill(BLACK)
        # Zeichne den TRON-Titel oben in der oberen Bildschirmhälfte
        if title_image:
            screen.blit(title_image, title_rect)
        
        # Zeichne die Schlangenköpfe (Puls-Effekt)
        for p in players:
            if p.highlighted:
                elapsed = time.time() - p.highlight_start_time
                if elapsed < 1:
                    pulse_size = int(p.circle_size * (1 + 0.5 * math.sin(elapsed * 10)))
                    pygame.draw.circle(screen, WHITE, (int(p.trail[0][0]), int(p.trail[0][1])), pulse_size)
                else:
                    p.highlighted = False
            pygame.draw.circle(screen, p.color, (int(p.trail[0][0]), int(p.trail[0][1])), p.circle_size)
        
        # Starttext (jetzt unter dem TRON-Titel)
        start_text = large_font.render("Drücke LEERTASTE zum Starten", True, WHITE)
        screen.blit(start_text, (DESKTOP_W // 2 - 250, DESKTOP_H // 2 - 50))
        
        # Texte für die Einstellungen
        speed_text = font.render(f"Geschwindigkeit: {speed}", True, WHITE)
        speed_rect = speed_text.get_rect(center=speed_text_center)
        screen.blit(speed_text, speed_rect)
        
        snake_text = font.render(f"Schlangenbreite: {snake_width}", True, WHITE)
        snake_rect = snake_text.get_rect(center=snake_text_center)
        screen.blit(snake_text, snake_rect)
        
        turn_speed_text = font.render(f"Drehgeschwindigkeit: {turn_speed}", True, WHITE)
        turn_speed_rect = turn_speed_text.get_rect(center=turn_speed_text_center)
        screen.blit(turn_speed_text, turn_speed_rect)
        
        zoom_text = font.render(f"Zoom: {zoom_slider.value:.2f}", True, WHITE)
        zoom_rect = zoom_text.get_rect(center=zoom_text_center)
        screen.blit(zoom_text, zoom_rect)
        
        # Buttons zeichnen
        for btn in speed_button_list:
            btn.update()
            btn.draw(screen, button_font)
        for btn in snake_button_list:
            btn.update()
            btn.draw(screen, button_font)
        for btn in turn_speed_button_list:
            btn.update()
            btn.draw(screen, button_font)
        zoom_slider.draw(screen)
        
        pygame.display.flip()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return None, None, None, None, None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    confirmed_players = [p for p in players if p.confirmed]
                    if confirmed_players:
                        # Rückgabe: Spieler, Speed, Schlangenbreite, Zoom und Drehgeschwindigkeit
                        return confirmed_players, speed, snake_width, zoom_slider.value, turn_speed
                if event.key == pygame.K_a and players[0].control_type == "keyboard":
                    players[0].confirmed = True
                    players[0].highlighted = True
                    players[0].highlight_start_time = time.time()
                if event.key == pygame.K_x:
                    players[0].confirmed = True
                    players[0].highlighted = True
                    players[0].highlight_start_time = time.time()
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return None, None, None, None, None
            for btn in speed_button_list + snake_button_list + turn_speed_button_list:
                btn.handle_event(event)
            zoom_slider.handle_event(event)
            if event.type == pygame.JOYBUTTONDOWN:
                for p in players:
                    if p.controller and event.joy == p.controller.get_instance_id():
                        if event.button in [0, 1, 2, 3]:
                            p.confirmed = True
                            p.highlighted = True
                            p.highlight_start_time = time.time()


# --- Spieler initialisieren (hier wird auch Schlangenbreite und Drehgeschwindigkeit gesetzt) ---
def init_players(players, snake_width, turn_speed):
    head_img = load_image("bike.png", (int(BLOCK_SIZE * 5), int(BLOCK_SIZE * 5)))
    # Weisen wir z. B. dem ersten Spieler dieses Bild zu:
    if head_img is not None:
        players[0].head_image = head_img
    num_players = len(players)
    positions, directions = generate_start_positions(num_players, DESKTOP_W, DESKTOP_H)
    for i, p in enumerate(players):
        # Setze die Startposition für den Kopf:
        p.head = [positions[i][0], positions[i][1]]
        # Erstelle den initialen Trail (zum Beispiel nur den Startpunkt – später wird der Trail erweitert)
        p.trail = [[positions[i][0], positions[i][1]]]
        p.dx, p.dy = directions[i]
        p.circle_size = snake_width
        p.turn_speed = turn_speed
    return players


def draw_snake_line(surface, player, zoom):
    """
    Zeichnet den Trail des Spielers als durchgehende Linie mit Lücken.
    Falls zwei aufeinanderfolgende Segmente zu weit auseinander liegen (Screen Wrap),
    wird die Linie dort unterbrochen.
    """
    segments = []       # Hier sammeln wir Teillinien
    current_segment = []  # Aktuelle Teillinie

    # Definiere einen Schwellwert, ab dem wir annehmen, dass ein Wrap erfolgt ist.
    # Dieser Wert hängt von BLOCK_SIZE, zoom und ggf. Spielwelt ab.
    threshold = BLOCK_SIZE * zoom * 2  # Beispiel: doppelte Blockgröße

    # Iteriere über den Trail
    for i, pos in enumerate(player.trail):
        # Transformiere die Position
        x = int(pos[0] * zoom)
        y = int(pos[1] * zoom)
        if current_segment:
            last_x, last_y = current_segment[-1]
            # Berechne den Abstand zum letzten Punkt
            dist = math.hypot(x - last_x, y - last_y)
            # Falls der Abstand zu groß ist, wird die Linie unterbrochen
            if dist > threshold:
                segments.append(current_segment)
                current_segment = []
        current_segment.append((x, y))
    if current_segment:
        segments.append(current_segment)

    # Zeichne die einzelnen Linienabschnitte
    thickness = max(1, int(player.circle_size * zoom))
    for seg in segments:
        if len(seg) >= 2:
            pygame.draw.lines(surface, player.color, False, seg, thickness)


# --- Game-Loop (Zoom wird angewendet) ---
def game_loop(players, speed, zoom):
    # Berechne die Weltgröße, die sich am Zoom-Faktor orientiert:
    world_width = DESKTOP_W / zoom
    world_height = DESKTOP_H / zoom
    play_music("theme.mp3")
    screen = pygame.display.set_mode((DESKTOP_W, DESKTOP_H), pygame.FULLSCREEN)
    start_time = time.time()
    running = True
    countdown(screen)
    
    while running:
        screen.fill(BLACK)
        
        # Optional: Zeichne einen statischen Hintergrund oder einen Rahmen,
        # der immer den gesamten Bildschirm ausfüllt.
        # pygame.draw.rect(screen, DARK_GRAY, (0, 0, DESKTOP_W, 50))
        # pygame.draw.rect(screen, DARK_GRAY, (0, 0, 50, DESKTOP_H))
        # pygame.draw.rect(screen, DARK_GRAY, (0, DESKTOP_H - 50, DESKTOP_W, 50))
        # pygame.draw.rect(screen, DARK_GRAY, (DESKTOP_W - 50, 0, 50, DESKTOP_H))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            handle_input(event, players)
        
        # Aktualisiere Position und Kollisionsprüfung anhand der Weltgrenzen
        for p in players:
            if p.turn_left:
                p.angle -= p.turn_speed
            if p.turn_right:
                p.angle += p.turn_speed
            
            # Aktualisiere die Bewegungsrichtung basierend auf dem Winkel
            p.dx = BLOCK_SIZE * math.cos(p.angle)
            p.dy = BLOCK_SIZE * math.sin(p.angle)
            
            p.update_position(world_width, world_height)
            p.check_collision(players, zoom)  # Falls du hier den Zoom in der Kollisionsprüfung nutzen möchtest
        
        elapsed = time.time() - start_time
        timer_text = font.render(f"Zeit: {int(elapsed)}s", True, WHITE)
        screen.blit(timer_text, (DESKTOP_W - 200, 10))
        
        # Zeichne alle Spielobjekte: Wandle Weltkoordinaten in Bildschirmkoordinaten um.
        for p in players:
            draw_snake_line(screen, p, zoom)
            # Zeichne den Kopf als zusätzlichen Kreis
            hx = int(p.head[0] * zoom)
            hy = int(p.head[1] * zoom)
            pygame.draw.circle(screen, p.color, (hx, hy), int(p.circle_size * zoom))
        if p.head_image is not None:
            # Optional: Skaliere das Bild entsprechend
            head_img = pygame.transform.scale(p.head_image, (int(p.circle_size * 2 * zoom), int(p.circle_size * 2 * zoom)))
            # Zentriere das Bild am Kopf
            hx = int(p.head[0] * zoom) - head_img.get_width() // 2
            hy = int(p.head[1] * zoom) - head_img.get_height() // 2
            screen.blit(head_img, (hx, hy))
        else:
            hx = int(p.head[0] * zoom)
            hy = int(p.head[1] * zoom)
            pygame.draw.circle(screen, p.color, (hx, hy), int(p.circle_size * zoom))

        
        pygame.draw.rect(screen, GRAY, (0, 0, DESKTOP_W, 50))
        x_pos = 10
        for i, p in enumerate(players):
            status = f"S{i+1}" if p.alive else "G/O"
            txt = font.render(status, True, p.color)
            screen.blit(txt, (x_pos, 10))
            x_pos += 150
        
        pygame.display.flip()
        clock.tick(speed)


def handle_input(event, players):
    if event.type == pygame.KEYDOWN:
        p = players[0]
        if event.key == pygame.K_LEFT:
            p.turn_left = True
        elif event.key == pygame.K_RIGHT:
            p.turn_right = True
    elif event.type == pygame.KEYUP:
        p = players[0]
        if event.key == pygame.K_LEFT:
            p.turn_left = False
        elif event.key == pygame.K_RIGHT:
            p.turn_right = False
    if event.type == pygame.JOYBUTTONDOWN:
        for p in players:
            if p.controller and event.joy == p.controller.get_instance_id():
                if event.button == 13:
                    p.turn_left = True
                    p.turn_right = False
                elif event.button == 14:
                    p.turn_right = True
                    p.turn_left = False
    if event.type == pygame.JOYBUTTONUP:
        for p in players:
            if p.controller and event.joy == p.controller.get_instance_id():
                if event.button == 13:
                    p.turn_left = False
                elif event.button == 14:
                    p.turn_right = False


def countdown(screen):
    for i in range(3, 0, -1):
        screen.fill(BLACK)
        text = large_font.render(str(i), True, WHITE)
        screen.blit(text, (DESKTOP_W // 2 - 20, DESKTOP_H // 2 - 50))
        pygame.display.flip()
        time.sleep(1/3)  # ca. 0,33 Sekunden pro Zahl


def end_screen(winner):
    screen = pygame.display.set_mode((DESKTOP_W, DESKTOP_H), pygame.FULLSCREEN)
    while True:
        screen.fill(BLACK)
        if winner:
            text = large_font.render(f"Spieler {players.index(winner) + 1} gewinnt!", True, winner.color)
        else:
            text = large_font.render("Zeit abgelaufen!", True, WHITE)
        screen.blit(text, (DESKTOP_W // 2 - 200, DESKTOP_H // 2 - 50))
        txt2 = font.render("Drücke ESC für Startmenü", True, WHITE)
        screen.blit(txt2, (DESKTOP_W // 2 - 150, DESKTOP_H // 2 + 50))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return


# --- Hauptprogramm ---
while True:
    res = start_screen()
    if res is not None:
        players, speed, snake_width, zoom, turn_speed = res
        players = init_players(players, snake_width, turn_speed)
        game_loop(players, speed, zoom)
    else:
        pygame.display.quit()
        exit()