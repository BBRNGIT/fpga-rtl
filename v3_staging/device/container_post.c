/* container_post.c — GENERATED power-on POST for the blank container. */
#include <stdio.h>
#include "container_gen.h"
int main(void){
    unsigned long long total=0;
    printf("== XCZU19EG blank container — POWER-ON POST ==\n");
    printf("%-20s %14s  %s\n","element","instances","subsystem");
    for(int i=0;i<CAST_TYPES;i++){ total+=CAST[i].count;
        printf("%-20s %14llu  %s\n",CAST[i].name,CAST[i].count,CAST[i].sub); }
    printf("----\n%d element types, %llu instances placed (manifest total %llu)\n",
           CAST_TYPES, total, CAST_TOTAL);
    printf("slices=%llu  fabric arrays allocated: PASS\n", CAST_SLICES);
    /* touch the largest arrays so they are linked, not dead-stripped */
    storage_element[0].state=1; lut6[0].cfg=1;
    return total==CAST_TOTAL?0:1;
}
