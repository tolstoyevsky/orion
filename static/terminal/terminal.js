import { Display } from './primitives/display';
import { Input } from './primitives/input';
import { Screen } from './primitives/screen';

export class Terminal {
    constructor($basis, row = 24, col = 80) {
        const _fit_screen_size = (row, col) => {
            const cell = this.display.getCellSize();
            const width = col * cell.width;
            const height = row * cell.height;

            this.screen.setSize(width, height);
        };

        this.screen = new Screen($basis);
        this.display = new Display(this.screen.$node, row, col);

        this.display.bind('onready', function() {
            _fit_screen_size(row, col);
        });

        const _input = new Input(this.screen.$node);
        const _ws = new WebSocket('ws://' + location.host + '/termsocket');

        _input.bind('oninput', function(data) {
            _ws.send(data);
        });

        _ws.onmessage = (e => {
            this.display.$node.innerHTML = e.data;
        });
    }
};
