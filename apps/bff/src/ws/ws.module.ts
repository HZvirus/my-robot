import { Module } from '@nestjs/common';
import { WsRegistrar } from './ws.registrar';

@Module({
    providers: [WsRegistrar],
    exports: [WsRegistrar],
})
export class WsModule { }
