\* GDP_Maximization *\
Maximize
OBJ: 2500 R1_B108 + 2500 R1_B11 + 2500 R1_B14 + 750 R1_B325 + 825 R1_B377
 + 1650 R1_B379 + 1250 R1_B382 + 400 R1_B386 + 1450 R1_B388 + 2000 R1_B390
 + 600 R1_B394 + 900 R1_B403 + 2000 R1_B404 + 1250 R1_B95 + 2500 R2_B108
 + 1650 R2_B18 + 1650 R2_B21 + 500 R2_B24 + 650 R2_B27 + 1250 R2_B30
 + 300 R2_B399 + 825 R2_B436 + 80 R2_B5 + 1250 R2_B95 + 1650 R3_B18
 + 1650 R3_B21 + 500 R3_B24 + 650 R3_B27 + 1250 R3_B30 + 300 R3_B399
 + 825 R3_B436 + 80 R3_B5 + 3000 R3_B56 + 2500 R3_B59
Subject To
Max_Buildings_R1_Constraint: R1_B108 + R1_B11 + R1_B14 + R1_B173 + R1_B180
 + R1_B184 + R1_B194 + R1_B258 + R1_B259 + R1_B263 + R1_B266 + R1_B279
 + R1_B282 + R1_B290 + R1_B291 + R1_B302 + R1_B310 + R1_B311 + R1_B312
 + R1_B313 + R1_B314 + R1_B322 + R1_B325 + R1_B333 + R1_B334 + R1_B338
 + R1_B341 + R1_B350 + R1_B358 + R1_B365 + R1_B366 + R1_B377 + R1_B379
 + R1_B382 + R1_B386 + R1_B388 + R1_B390 + R1_B394 + R1_B403 + R1_B404
 + R1_B408 + R1_B431 + R1_B439 + R1_B445 + R1_B449 + R1_B95 <= 6
Max_Buildings_R2_Constraint: R2_B108 + R2_B18 + R2_B21 + R2_B24 + R2_B258
 + R2_B259 + R2_B27 + R2_B270 + R2_B286 + R2_B295 + R2_B298 + R2_B30 + R2_B306
 + R2_B318 + R2_B329 + R2_B345 + R2_B354 + R2_B373 + R2_B374 + R2_B399
 + R2_B436 + R2_B453 + R2_B5 + R2_B95 <= 4
Max_Buildings_R3_Constraint: R3_B18 + R3_B21 + R3_B24 + R3_B258 + R3_B259
 + R3_B27 + R3_B270 + R3_B286 + R3_B295 + R3_B298 + R3_B30 + R3_B306 + R3_B318
 + R3_B329 + R3_B345 + R3_B354 + R3_B373 + R3_B374 + R3_B399 + R3_B436
 + R3_B453 + R3_B5 + R3_B56 + R3_B59 <= 4
P1_Food_Constraint: - 125 R1_B173 - 125 R1_B180 - 125 R1_B184 - 125 R1_B194
 + 50 R1_B266 - 80 R1_B290 - 140 R1_B291 - 80 R1_B302 - 125 R1_B310
 - 125 R1_B311 - 125 R1_B312 - 125 R1_B313 - 125 R1_B314 - 125 R1_B322
 - 125 R1_B325 - 125 R1_B365 - 125 R1_B366 - 100 R1_B377 - 100 R1_B379
 - 80 R1_B382 + 90 R1_B386 - 140 R1_B394 - 100 R1_B403 - 100 R1_B404
 - 75 R1_B408 - 80 R1_B445 - 80 R1_B449 + 90 R1_B95 + 70 R2_B24 + 50 R2_B27
 + 50 R2_B30 - 40 R2_B329 - 50 R2_B373 - 50 R2_B374 - 80 R2_B399 - 40 R2_B436
 - 50 R2_B453 + 40 R2_B5 + 90 R2_B95 + 70 R3_B24 + 50 R3_B27 + 50 R3_B30
 - 40 R3_B329 - 50 R3_B373 - 50 R3_B374 - 80 R3_B399 - 40 R3_B436 - 50 R3_B453
 + 40 R3_B5 >= 0
P1_Public_Order_Constraint: - 6 R1_B108 - 10 R1_B11 - 10 R1_B14 + 10 R1_B173
 + 10 R1_B180 + 10 R1_B184 + 10 R1_B194 + 10 R1_B258 + 15 R1_B259 + 10 R1_B263
 + 8 R1_B279 + 5 R1_B290 + 6 R1_B291 + 5 R1_B302 + 10 R1_B310 + 10 R1_B311
 + 10 R1_B312 + 10 R1_B313 + 8 R1_B314 - 20 R1_B322 + 10 R1_B333 + 15 R1_B334
 + 10 R1_B338 + 12 R1_B365 + 12 R1_B366 + 21 R1_B377 + 13 R1_B379 - 4 R1_B386
 - 4 R1_B388 - 4 R1_B390 + 5 R1_B394 + 17 R1_B403 + 18 R1_B404 + 3 R1_B408
 + 4 R1_B431 + 9 R1_B445 + 5 R1_B449 - 6 R1_B95 - 6 R2_B108 - 10 R2_B18
 - 10 R2_B21 - 5 R2_B24 + 10 R2_B258 + 15 R2_B259 - 5 R2_B27 + 5 R2_B270
 + 5 R2_B286 + 3 R2_B298 - 5 R2_B30 - 10 R2_B329 + 5 R2_B345 + 4 R2_B373
 + 9 R2_B374 + 3 R2_B399 + 4 R2_B436 + 4 R2_B453 - 5 R2_B5 - 6 R2_B95
 - 10 R3_B18 - 10 R3_B21 - 5 R3_B24 + 10 R3_B258 + 15 R3_B259 - 5 R3_B27
 + 5 R3_B270 + 5 R3_B286 + 3 R3_B298 - 5 R3_B30 - 10 R3_B329 + 5 R3_B345
 + 4 R3_B373 + 9 R3_B374 + 3 R3_B399 + 4 R3_B436 + 4 R3_B453 - 5 R3_B5
 - 15 R3_B56 - 15 R3_B59 >= 0
P1_Sanitation_Constraint_att_reg_aegyptus_alexandria_Constraint: - 6 R1_B108
 - 10 R1_B11 - 10 R1_B14 + 15 R1_B282 + 9 R1_B358 - 4 R1_B377 - 2 R1_B379
 - 6 R1_B386 - 6 R1_B388 - 6 R1_B390 - 4 R1_B394 + 16 R1_B431 + 18 R1_B439
 - 6 R1_B95 + 3 R2_B295 + 3 R2_B306 + 7 R2_B436 + 3 R3_B295 + 3 R3_B306
 + 7 R3_B436 >= 1
P1_Sanitation_Constraint_att_reg_aegyptus_berenice_Constraint: 4 R1_B358
 + 16 R1_B431 + 6 R1_B439 - 6 R2_B108 - 10 R2_B18 - 10 R2_B21 - 5 R2_B24
 - 5 R2_B27 + 3 R2_B295 - 5 R2_B30 + 3 R2_B306 - 2 R2_B399 + 13 R2_B436
 - 5 R2_B5 - 6 R2_B95 + 3 R3_B295 + 3 R3_B306 + 7 R3_B436 >= 1
P1_Sanitation_Constraint_att_reg_aegyptus_oxyrhynchus_Constraint: 4 R1_B358
 + 16 R1_B431 + 6 R1_B439 + 3 R2_B295 + 3 R2_B306 + 7 R2_B436 - 10 R3_B18
 - 10 R3_B21 - 5 R3_B24 - 5 R3_B27 + 3 R3_B295 - 5 R3_B30 + 3 R3_B306
 - 2 R3_B399 + 13 R3_B436 - 5 R3_B5 - 10 R3_B56 - 10 R3_B59 >= 1
R1_Chain_BC10_Constraint: R1_B263 <= 1
R1_Chain_BC11_Constraint: R1_B266 <= 1
R1_Chain_BC12_Constraint: R1_B279 <= 1
R1_Chain_BC13_Constraint: R1_B282 <= 1
R1_Chain_BC14_Constraint: R1_B290 + R1_B291 <= 1
R1_Chain_BC15_Constraint: R1_B302 <= 1
R1_Chain_BC16_Constraint: R1_B310 + R1_B311 + R1_B312 + R1_B313 + R1_B314 <= 1
R1_Chain_BC17_Constraint: R1_B322 <= 1
R1_Chain_BC18_Constraint: R1_B325 <= 1
R1_Chain_BC19_Constraint: R1_B333 + R1_B334 <= 1
R1_Chain_BC1_Constraint: R1_B11 <= 1
R1_Chain_BC20_Constraint: R1_B338 <= 1
R1_Chain_BC21_Constraint: R1_B341 <= 1
R1_Chain_BC22_Constraint: R1_B350 <= 1
R1_Chain_BC23_Constraint: R1_B358 <= 1
R1_Chain_BC24_Constraint: R1_B365 <= 1
R1_Chain_BC25_Constraint: R1_B366 <= 1
R1_Chain_BC26_Constraint: R1_B377 <= 1
R1_Chain_BC27_Constraint: R1_B379 <= 1
R1_Chain_BC28_Constraint: R1_B382 <= 1
R1_Chain_BC29_Constraint: R1_B386 <= 1
R1_Chain_BC2_Constraint: R1_B14 <= 1
R1_Chain_BC30_Constraint: R1_B388 <= 1
R1_Chain_BC31_Constraint: R1_B390 <= 1
R1_Chain_BC32_Constraint: R1_B394 <= 1
R1_Chain_BC33_Constraint: R1_B403 <= 1
R1_Chain_BC34_Constraint: R1_B404 <= 1
R1_Chain_BC35_Constraint: R1_B408 <= 1
R1_Chain_BC36_Constraint: R1_B431 <= 1
R1_Chain_BC37_Constraint: R1_B439 <= 1
R1_Chain_BC38_Constraint: R1_B445 <= 1
R1_Chain_BC39_Constraint: R1_B449 <= 1
R1_Chain_BC3_Constraint: R1_B95 <= 1
R1_Chain_BC4_Constraint: R1_B108 <= 1
R1_Chain_BC5_Constraint: R1_B173 <= 1
R1_Chain_BC6_Constraint: R1_B180 <= 1
R1_Chain_BC7_Constraint: R1_B184 <= 1
R1_Chain_BC8_Constraint: R1_B194 <= 1
R1_Chain_BC9_Constraint: R1_B258 + R1_B259 <= 1
R1_Major_Constraint: R1_B394 = 1
R1_Port_Constraint: R1_B108 + R1_B95 = 1
R1_Religion_orthodox_legendary_Resource_Constraint: R1_B333 + R1_B334 = 1
R2_Chain_BC40_Constraint: R2_B5 <= 1
R2_Chain_BC41_Constraint: R2_B18 <= 1
R2_Chain_BC42_Constraint: R2_B21 <= 1
R2_Chain_BC43_Constraint: R2_B24 <= 1
R2_Chain_BC44_Constraint: R2_B27 <= 1
R2_Chain_BC45_Constraint: R2_B30 <= 1
R2_Chain_BC46_Constraint: R2_B95 <= 1
R2_Chain_BC47_Constraint: R2_B108 <= 1
R2_Chain_BC48_Constraint: R2_B258 + R2_B259 <= 1
R2_Chain_BC49_Constraint: R2_B270 <= 1
R2_Chain_BC50_Constraint: R2_B286 <= 1
R2_Chain_BC51_Constraint: R2_B295 <= 1
R2_Chain_BC52_Constraint: R2_B298 <= 1
R2_Chain_BC53_Constraint: R2_B306 <= 1
R2_Chain_BC54_Constraint: R2_B318 <= 1
R2_Chain_BC55_Constraint: R2_B329 <= 1
R2_Chain_BC56_Constraint: R2_B345 <= 1
R2_Chain_BC57_Constraint: R2_B354 <= 1
R2_Chain_BC58_Constraint: R2_B373 <= 1
R2_Chain_BC59_Constraint: R2_B374 <= 1
R2_Chain_BC60_Constraint: R2_B399 <= 1
R2_Chain_BC61_Constraint: R2_B436 <= 1
R2_Chain_BC62_Constraint: R2_B453 <= 1
R2_Minor_Constraint: R2_B399 = 1
R2_Port_Constraint: R2_B108 + R2_B95 = 1
R3_Chain_BC63_Constraint: R3_B5 <= 1
R3_Chain_BC64_Constraint: R3_B18 <= 1
R3_Chain_BC65_Constraint: R3_B21 <= 1
R3_Chain_BC66_Constraint: R3_B24 <= 1
R3_Chain_BC67_Constraint: R3_B27 <= 1
R3_Chain_BC68_Constraint: R3_B30 <= 1
R3_Chain_BC69_Constraint: R3_B56 <= 1
R3_Chain_BC70_Constraint: R3_B59 <= 1
R3_Chain_BC71_Constraint: R3_B258 + R3_B259 <= 1
R3_Chain_BC72_Constraint: R3_B270 <= 1
R3_Chain_BC73_Constraint: R3_B286 <= 1
R3_Chain_BC74_Constraint: R3_B295 <= 1
R3_Chain_BC75_Constraint: R3_B298 <= 1
R3_Chain_BC76_Constraint: R3_B306 <= 1
R3_Chain_BC77_Constraint: R3_B318 <= 1
R3_Chain_BC78_Constraint: R3_B329 <= 1
R3_Chain_BC79_Constraint: R3_B345 <= 1
R3_Chain_BC80_Constraint: R3_B354 <= 1
R3_Chain_BC81_Constraint: R3_B373 <= 1
R3_Chain_BC82_Constraint: R3_B374 <= 1
R3_Chain_BC83_Constraint: R3_B399 <= 1
R3_Chain_BC84_Constraint: R3_B436 <= 1
R3_Chain_BC85_Constraint: R3_B453 <= 1
R3_Gold_Resource_Constraint: R3_B56 + R3_B59 <= 1
R3_Minor_Constraint: R3_B399 = 1
Binaries
R1_B108
R1_B11
R1_B14
R1_B173
R1_B180
R1_B184
R1_B194
R1_B258
R1_B259
R1_B263
R1_B266
R1_B279
R1_B282
R1_B290
R1_B291
R1_B302
R1_B310
R1_B311
R1_B312
R1_B313
R1_B314
R1_B322
R1_B325
R1_B333
R1_B334
R1_B338
R1_B341
R1_B350
R1_B358
R1_B365
R1_B366
R1_B377
R1_B379
R1_B382
R1_B386
R1_B388
R1_B390
R1_B394
R1_B403
R1_B404
R1_B408
R1_B431
R1_B439
R1_B445
R1_B449
R1_B95
R2_B108
R2_B18
R2_B21
R2_B24
R2_B258
R2_B259
R2_B27
R2_B270
R2_B286
R2_B295
R2_B298
R2_B30
R2_B306
R2_B318
R2_B329
R2_B345
R2_B354
R2_B373
R2_B374
R2_B399
R2_B436
R2_B453
R2_B5
R2_B95
R3_B18
R3_B21
R3_B24
R3_B258
R3_B259
R3_B27
R3_B270
R3_B286
R3_B295
R3_B298
R3_B30
R3_B306
R3_B318
R3_B329
R3_B345
R3_B354
R3_B373
R3_B374
R3_B399
R3_B436
R3_B453
R3_B5
R3_B56
R3_B59
End
