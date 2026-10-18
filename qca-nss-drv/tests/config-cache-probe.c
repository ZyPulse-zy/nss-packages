/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
int main(void)
{
#ifdef NSS_FIRMWARE_VERSION_12_5
	puts("12.5");
#else
	puts("12.x");
#endif
	return 0;
}
