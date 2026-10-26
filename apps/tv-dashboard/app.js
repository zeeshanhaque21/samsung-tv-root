(function () {
    'use strict';
    var tv = window.tizen;
    var buttons = [];
    var selected = 0;
    var inputActive = false;
    var dialogOpen = false;
    var busy = false;
    var pendingInput = false;
    var generation = 0;
    var timer;
    var hintTimer;
    var inputWindow = tv && tv.tvwindow;
    var status = document.getElementById('status');
    var dialog = document.getElementById('exit-dialog');
    var stay = document.getElementById('stay');
    var leave = document.getElementById('leave');

    function message(text) { status.textContent = text; }
    function errorName(error) { return error && error.name ? error.name : 'UnknownError'; }
    function focus(index) {
        selected = index;
        buttons[index].focus();
    }
    function finish(token) {
        if (token !== generation) { return false; }
        window.clearTimeout(timer);
        busy = false;
        pendingInput = false;
        generation += 1;
        return true;
    }
    function begin(label, cleanup, inputOperation) {
        busy = true;
        pendingInput = !!inputOperation;
        generation += 1;
        var token = generation;
        message(label);
        timer = window.setTimeout(function () {
            if (finish(token)) {
                message('No response from the TV. Try again or use the TV Source menu.');
                if (cleanup) { cleanup(); }
            }
        }, 10000);
        return token;
    }
    function closeInput(originalMessage) {
        var token = begin(originalMessage || 'Returning to TV Home...', function () {
            inputActive = true;
            message('HDMI close not confirmed. Press Back to retry, or use the TV Source menu.');
        }, true);
        function failed(error) {
            if (finish(token)) {
                inputActive = true;
                document.body.className = '';
                document.getElementById('input-hint').hidden = true;
                message((originalMessage ? originalMessage + ' ' : '') + 'HDMI close failed (' + errorName(error) + '). Press Back to retry or use the TV Source menu.');
            }
        }
        try {
            inputWindow.hide(function () {
                if (finish(token)) {
                    restoreHome();
                    message(originalMessage || 'Back at TV Home.');
                }
            }, failed, 'MAIN');
        } catch (error) { failed(error); }
    }
    function showInputHint() {
        document.getElementById('input-hint').hidden = false;
        window.clearTimeout(hintTimer);
        hintTimer = window.setTimeout(function () {
            document.getElementById('input-hint').hidden = true;
        }, 5000);
    }
    function restoreHome() {
        window.clearTimeout(hintTimer);
        inputActive = false;
        document.body.className = '';
        document.getElementById('input-hint').hidden = true;
        focus(selected);
    }
    function launch(app) {
        if (!tv || !tv.application || !tv.application.launch) {
            message('Demo: cannot open ' + app.name + '. Run on a Samsung TV and configure its application ID in settings.js.');
            return;
        }
        if (!app.id) {
            message(app.name + ': setup required. Add the installed application ID to settings.js, then rebuild and sign.');
            return;
        }
        var token = begin('Opening ' + app.name + '...');
        try {
            tv.application.launch(app.id, function () {
                if (finish(token)) { message('Launch accepted for ' + app.name + '. Use the TV remote to return.'); }
            }, function (error) {
                if (finish(token)) { message('Cannot open ' + app.name + ' (' + errorName(error) + '). Check the installed app ID and availability.'); }
            });
        } catch (error) {
            if (finish(token)) { message('Cannot open ' + app.name + ' (' + errorName(error) + '). Check the app ID and launch permission.'); }
        }
    }
    function hdmi(number) {
        if (!inputWindow) {
            message('Demo: cannot switch HDMI ' + number + '. Run on a Samsung TV, or use the TV Source menu.');
            return;
        }
        var showAttempted = false;
        var token = begin('Opening HDMI ' + number + '...', function () {
            if (showAttempted) { closeInput('No response from HDMI.'); }
        }, true);
        function fail(error) {
            if (finish(token)) {
                var text = 'Cannot open HDMI ' + number + ' (' + errorName(error) + '). Check the cable or use the TV Source menu.';
                if (showAttempted) { closeInput(text); }
                else { message(text); }
            }
        }
        try {
            tv.systeminfo.getPropertyValue('VIDEOSOURCE', function (videoSources) {
                if (token !== generation) { return; }
                var sources = videoSources.connected.concat(videoSources.disconnected);
                var source = null;
                var i;
                for (i = 0; i < sources.length; i += 1) {
                    if (sources[i].type === 'HDMI' && sources[i].number === number) { source = sources[i]; break; }
                }
                if (!source) { fail({ name: 'InputUnavailable' }); return; }
                try {
                    inputWindow.setSource(source, function () {
                        if (token !== generation) { return; }
                        try {
                            showAttempted = true;
                            inputWindow.show(function () {
                                if (!finish(token)) {
                                    if (!busy && !inputActive) { closeInput('Late HDMI response. Returned to TV Home.'); }
                                    return;
                                }
                                inputActive = true;
                                document.body.className = 'input-active';
                                document.getElementById('input-number').textContent = number;
                                showInputHint();
                                message('HDMI ' + number + ' selected.');
                            }, fail, ['0px', '0px', '1920px', '1080px'], 'MAIN', 'BEHIND');
                        } catch (error) { fail(error); }
                    }, fail, 'MAIN');
                } catch (error) { fail(error); }
            }, fail);
        } catch (error) { fail(error); }
    }
    function addTile(parent, name, style, subtitle, action, input) {
        var button = document.createElement('button');
        var brand = document.createElement('span');
        var note = document.createElement(input ? 'small' : 'span');
        var index = buttons.length;
        button.type = 'button';
        button.className = 'tile ' + style;
        button.setAttribute('aria-label', name + '. ' + subtitle);
        if (input) {
            var port = document.createElement('span');
            port.className = 'port';
            port.setAttribute('aria-hidden', 'true');
            button.appendChild(port);
        }
        brand.className = 'brand';
        brand.textContent = name;
        note.className = input ? '' : 'setup';
        note.textContent = subtitle;
        button.appendChild(brand);
        button.appendChild(note);
        button.addEventListener('focus', function () { selected = index; });
        button.addEventListener('click', function () { if (!busy) { action(); } });
        parent.appendChild(button);
        buttons.push(button);
    }
    window.TV_HOME_APPS.forEach(function (app) {
        addTile(document.getElementById('apps'), app.name, app.style, app.id ? 'Open app' : 'Setup required', function () { launch(app); }, false);
    });
    [1, 2].forEach(function (number) {
        addTile(document.getElementById('inputs'), 'HDMI ' + number, 'input', 'External input', function () { hdmi(number); }, true);
    });
    function verticalFocus(start, end) {
        var from = buttons[selected].getBoundingClientRect();
        var center = (from.left + from.right) / 2;
        var closest = start;
        var distance = Infinity;
        var i;
        for (i = start; i < end; i += 1) {
            var rect = buttons[i].getBoundingClientRect();
            var difference = Math.abs((rect.left + rect.right) / 2 - center);
            if (difference < distance) { closest = i; distance = difference; }
        }
        focus(closest);
    }
    function closeDialog() {
        dialogOpen = false;
        dialog.hidden = true;
        focus(selected);
    }
    stay.addEventListener('click', closeDialog);
    leave.addEventListener('click', function () {
        if (!tv || !tv.application) { closeDialog(); message('Demo: close this browser tab to leave. No TV app is running.'); return; }
        try { tv.application.getCurrentApplication().exit(); }
        catch (error) { closeDialog(); message('Cannot exit (' + errorName(error) + '). Use the Home button on your remote.'); }
    });
    document.addEventListener('keydown', function (event) {
        var key = event.keyCode;
        if ([37, 38, 39, 40, 13, 10009, 27, 8, 9].indexOf(key) === -1) { return; }
        event.preventDefault();
        if (busy) { return; }
        if (inputActive) {
            if (key === 10009 || key === 27 || key === 8) {
                closeInput();
            } else if (document.body.className === 'input-active') { showInputHint(); }
            return;
        }
        if (dialogOpen) {
            if (key === 10009 || key === 27 || key === 8) { closeDialog(); }
            else if (key === 37 || key === 39 || key === 9) { (document.activeElement === stay ? leave : stay).focus(); }
            else if (key === 13) { document.activeElement.click(); }
            return;
        }
        if (key === 10009 || key === 27 || key === 8) {
            dialogOpen = true;
            dialog.hidden = false;
            stay.focus();
        } else if (key === 13) { buttons[selected].click(); }
        else if (key === 37 && selected !== 0 && selected !== window.TV_HOME_APPS.length) { focus(selected - 1); }
        else if (key === 39 && selected !== window.TV_HOME_APPS.length - 1 && selected !== buttons.length - 1) { focus(selected + 1); }
        else if (key === 40 && selected < window.TV_HOME_APPS.length) { verticalFocus(window.TV_HOME_APPS.length, buttons.length); }
        else if (key === 38 && selected >= window.TV_HOME_APPS.length) { verticalFocus(0, window.TV_HOME_APPS.length); }
        else if (key === 9) { focus((selected + (event.shiftKey ? buttons.length - 1 : 1)) % buttons.length); }
    });
    function updateClock() {
        var now = new Date();
        var hours = now.getHours();
        var minutes = now.getMinutes();
        var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        var months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        document.getElementById('clock').textContent = (hours % 12 || 12) + ':' + (minutes < 10 ? '0' : '') + minutes + (hours < 12 ? ' AM' : ' PM');
        document.getElementById('date').textContent = days[now.getDay()] + ', ' + months[now.getMonth()] + ' ' + now.getDate();
    }
    document.addEventListener('visibilitychange', function () {
        if (document.hidden && (inputActive || pendingInput) && inputWindow) {
            window.clearTimeout(timer);
            closeInput();
        } else if (!document.hidden) {
            updateClock();
            if (!dialogOpen && !inputActive) { focus(selected); }
        }
    });
    window.addEventListener('unload', function () {
        if (inputWindow && (inputActive || pendingInput)) {
            try { inputWindow.hide(function () {}, function () {}, 'MAIN'); } catch (ignored) { /* Best effort on exit. */ }
        }
    });
    var deviceReady = tv && tv.application && typeof tv.application.launch === 'function' && inputWindow;
    document.getElementById('mode').textContent = deviceReady ? 'TV' : 'Demo';
    if (deviceReady) { message('Choose an app or HDMI input. App tiles marked Setup required need an installed application ID.'); }
    updateClock();
    window.setInterval(updateClock, 15000);
    focus(0);
}());
