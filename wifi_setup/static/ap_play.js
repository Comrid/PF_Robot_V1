/** AP play: Socket.IO joystick + camera + ultrasonic (no WebRTC). */
(function () {
    const socket = typeof io !== 'undefined'
        ? io({ transports: ['polling', 'websocket'], reconnection: true, reconnectionAttempts: 8 })
        : null;
    let controllerRunning = false;
    let isJoystickActive = false;
    let joystickRadius = 100;
    let currentX = 0, currentY = 0;
    let lastCommand = { x: 0, y: 0 };
    let commandInterval = null;
    let currentTab = 'camera';

    function joystickToCommand(x, y) {
        const ax = Math.abs(x), ay = Math.abs(y);
        let px = ax <= 0.2 ? 0 : x, py = ay <= 0.2 ? 0 : y;
        return {
            x: Math.max(-128, Math.min(127, Math.round(px * 127))),
            y: Math.max(-128, Math.min(127, Math.round(py * 127)))
        };
    }

    function sendJoystickCommand(x, y) {
        if (!controllerRunning || !socket) return;
        lastCommand = joystickToCommand(x, y);
        socket.emit('ap_joystick', lastCommand);
    }

    function startCommandInterval() {
        if (commandInterval) return;
        commandInterval = setInterval(function () {
            if (controllerRunning && socket) socket.emit('ap_joystick', lastCommand);
        }, 100);
    }

    function stopCommandInterval() {
        if (commandInterval) { clearInterval(commandInterval); commandInterval = null; }
    }

    function switchTab(tab) {
        currentTab = tab;
        const cam = document.getElementById('cameraTab');
        const us = document.getElementById('ultrasonicTab');
        const img = document.getElementById('cameraImage');
        const chart = document.getElementById('ultrasonicChart');
        const hint = document.getElementById('imageBoxText');
        if (tab === 'camera') {
            cam.classList.add('active'); us.classList.remove('active');
            img.style.display = img.classList.contains('active') ? 'block' : 'none';
            chart.style.display = 'none';
            hint.style.display = img.classList.contains('active') ? 'none' : 'block';
        } else {
            cam.classList.remove('active'); us.classList.add('active');
            img.style.display = 'none';
            chart.style.display = chart.classList.contains('active') ? 'block' : 'none';
            hint.style.display = chart.classList.contains('active') ? 'none' : 'block';
        }
    }

    function updateCamera(jpeg) {
        if (!jpeg) return;
        const img = document.getElementById('cameraImage');
        img.src = 'data:image/jpeg;base64,' + jpeg;
        img.classList.add('active');
        document.getElementById('imageBoxText').style.display = 'none';
        if (currentTab === 'camera') img.style.display = 'block';
    }

    let usHistory = [];
    function updateUltrasonic(val) {
        const n = parseFloat(val);
        if (isNaN(n)) return;
        usHistory.push(n);
        if (usHistory.length > 40) usHistory.shift();
        const canvas = document.getElementById('ultrasonicChart');
        const ctx = canvas.getContext('2d');
        const w = canvas.width = canvas.offsetWidth;
        const h = canvas.height = canvas.offsetHeight;
        ctx.fillStyle = 'rgba(15,23,42,0.9)';
        ctx.fillRect(0, 0, w, h);
        const maxV = Math.max(100, ...usHistory, 1);
        const barW = w / usHistory.length;
        usHistory.forEach(function (v, i) {
            const bh = (v / maxV) * (h - 30);
            ctx.fillStyle = '#4ade80';
            ctx.fillRect(i * barW, h - bh - 20, barW - 2, bh);
        });
        ctx.fillStyle = '#fff';
        ctx.font = '14px sans-serif';
        ctx.fillText(n.toFixed(1) + ' cm', 8, 18);
        canvas.classList.add('active');
        document.getElementById('imageBoxText').style.display = 'none';
        if (currentTab === 'ultrasonic') canvas.style.display = 'block';
    }

    function resizeJoystick() {
        const area = document.getElementById('joystickArea');
        if (!area) return;
        const rect = area.getBoundingClientRect();
        const size = Math.min(rect.width, rect.height);
        joystickRadius = Math.max(36, size / 2 - 28);
    }

    function handleMove(clientX, clientY) {
        const area = document.getElementById('joystickArea');
        const center = document.getElementById('joystickCenter');
        const rect = area.getBoundingClientRect();
        const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
        let dx = clientX - cx, dy = clientY - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > joystickRadius) { dx *= joystickRadius / dist; dy *= joystickRadius / dist; }
        center.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';
        currentX = dx / joystickRadius;
        currentY = -dy / joystickRadius;
        sendJoystickCommand(currentX, currentY);
    }

    function resetStick() {
        const center = document.getElementById('joystickCenter');
        center.classList.remove('active');
        center.style.transform = 'translate(-50%, -50%)';
        currentX = currentY = 0;
        sendJoystickCommand(0, 0);
    }

    function toggleController() {
        if (typeof io === 'undefined') {
            alert('Socket.IO 스크립트를 불러오지 못했습니다. 페이지를 새로고침해 주세요.');
            return;
        }
        if (!socket || !socket.connected) {
            alert('서버에 연결되지 않았습니다. 잠시 후 다시 시도해 주세요.');
            return;
        }
        const btn = document.getElementById('joystickToggleBtn');
        const txt = document.getElementById('joystickToggleText');
        if (!controllerRunning) {
            socket.emit('ap_play_start');
            controllerRunning = true;
            btn.classList.add('active');
            txt.textContent = '정지';
            startCommandInterval();
        } else {
            socket.emit('ap_play_stop');
            controllerRunning = false;
            btn.classList.remove('active');
            txt.textContent = '시작';
            stopCommandInterval();
            resetStick();
            isJoystickActive = false;
        }
    }

    if (socket) {
        socket.on('connect', function () {
            const hint = document.getElementById('imageBoxText');
            if (hint && !controllerRunning) hint.textContent = '시작을 누르면 화면이 표시됩니다';
        });
        socket.on('connect_error', function () {
            console.warn('AP play: socket connect_error');
        });
        socket.on('ap_play_status', function (d) {
            if (!d.running) {
                controllerRunning = false;
                const btn = document.getElementById('joystickToggleBtn');
                const txt = document.getElementById('joystickToggleText');
                if (btn) btn.classList.remove('active');
                if (txt) txt.textContent = '시작';
                stopCommandInterval();
                resetStick();
                if (d.error) alert(d.error);
            }
        });
        socket.on('ap_camera_frame', function (d) { if (d && d.jpeg) updateCamera(d.jpeg); });
        socket.on('ap_ultrasonic', function (d) { if (d && d.value != null) updateUltrasonic(d.value); });
        socket.on('disconnect', function () {
            controllerRunning = false;
            stopCommandInterval();
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById('cameraTab').onclick = function () { switchTab('camera'); };
        document.getElementById('ultrasonicTab').onclick = function () { switchTab('ultrasonic'); };
        document.getElementById('joystickToggleBtn').onclick = toggleController;
        resizeJoystick();
        window.addEventListener('resize', resizeJoystick);

        const area = document.getElementById('joystickArea');
        const center = document.getElementById('joystickCenter');
        function start(e) {
            if (!controllerRunning) return;
            e.preventDefault();
            isJoystickActive = true;
            center.classList.add('active');
            const t = e.touches ? e.touches[0] : e;
            handleMove(t.clientX, t.clientY);
        }
        function move(e) {
            if (!isJoystickActive) return;
            e.preventDefault();
            const t = e.touches ? e.touches[0] : e;
            handleMove(t.clientX, t.clientY);
        }
        function end() { if (!isJoystickActive) return; isJoystickActive = false; resetStick(); }
        area.addEventListener('touchstart', start, { passive: false });
        area.addEventListener('touchmove', move, { passive: false });
        area.addEventListener('touchend', end);
        area.addEventListener('mousedown', start);
        document.addEventListener('mousemove', function (e) { if (isJoystickActive) move(e); });
        document.addEventListener('mouseup', end);
    });
})();
