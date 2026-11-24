#ifndef MTP_H
#define MTP_H
#include <stdint.h>
int mtp_has_output(void);int mtp_has_event(void);int mtp_init(void);void mtp_reset(void);int mtp_can_receive(void);
void mtp_receive(const uint8_t*,uint8_t);int mtp_transmit(uint8_t*);int mtp_event(uint8_t*);unsigned mtp_phase(void);
#endif
