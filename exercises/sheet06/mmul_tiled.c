#include <stdio.h>
#include <stdlib.h>
#include <time.h>   // For timing
#include <string.h> // For atoi with error checking (strtol)

// Set matrix size to 2048
#define S 2048
#define N S
#define M S
#define K S

#define MIN(X, Y) ((X) < (Y) ? (X) : (Y))
#define MAX(X, Y) ((X) > (Y) ? (X) : (Y))

#define TYPE double
#define MATRIX TYPE **

// A utility function to create matrix
MATRIX createMatrix(unsigned x, unsigned y) {
    TYPE *data = malloc(x * y * sizeof(TYPE));
    if (data == NULL) {
        perror("Failed to allocate matrix data");
        exit(EXIT_FAILURE);
    }

    TYPE **index = malloc(x * sizeof(TYPE *));
    if (index == NULL) {
        perror("Failed to allocate matrix index");
        free(data);
        exit(EXIT_FAILURE);
    }

    index[0] = data;
    for (unsigned i = 1; i < x; ++i) {
        index[i] = &(data[i * y]);
    }
    return index;
}

void freeMatrix(MATRIX matrix) {
    if (matrix != NULL) {
        free(matrix[0]); // Free the contiguous data block
        free(matrix);    // Free the row pointers
    }
}

int main(int argc, char *argv[]) {
    int tile_size = 0; // Default: 0 indicates no tiling / original code path

    if (argc > 1) {
        char *endptr;
        long val = strtol(argv[1], &endptr, 10);
        // Check for errors: empty string, non-numeric chars, out of range
        if (endptr == argv[1] || *endptr != '\0' || val <= 0 || val > S) {
            fprintf(stderr, "Usage: %s [tile_size]\n", argv[0]);
            fprintf(stderr, "tile_size must be a positive integer <= %d\n", S);
            return EXIT_FAILURE;
        }
        tile_size = (int)val;
    }


    // create the matrices
    MATRIX A = createMatrix(N, M);
    MATRIX B = createMatrix(M, K);
    MATRIX C = createMatrix(N, K);

    // initialize the matrices

    // A contains real values
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < M; j++) {
            A[i][j] = (TYPE)(i * j % 100); 
        }
    }

    // B is the identity matrix
    for (int i = 0; i < M; i++) {
        for (int j = 0; j < K; j++) {
            B[i][j] = (i == j) ? 1.0 : 0.0;
        }
    }

    // Initialize C to zero - IMPORTANT for tiled version accumulation
    for (int i = 0; i < N; i++) {
        for (int j = 0; j < K; j++) {
            C[i][j] = 0.0;
        }
    }

    // conduct multiplication
    if (tile_size > 0) {
        for (int ii = 0; ii < N; ii += tile_size) {
            for (int jj = 0; jj < K; jj += tile_size) {
                for (int kk = 0; kk < M; kk += tile_size) {
                    // Inner loops iterate within the tile
                    int i_max = MIN(ii + tile_size, N);
                    int j_max = MIN(jj + tile_size, K);
                    int k_max = MIN(kk + tile_size, M);

                    for (int i = ii; i < i_max; ++i) {
                        for (int j = jj; j < j_max; ++j) {
                            for (int k = kk; k < k_max; ++k) {
                                C[i][j] += A[i][k] * B[k][j];
                            }
                        }
                    }
                }
            }
        }
    } else {
        // Original non-tiled version
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < K; j++) {
                TYPE sum = 0; // Original initializes sum here
                for (int k = 0; k < M; k++) {
                    sum += A[i][k] * B[k][j];
                }
                C[i][j] = sum; // Assign sum here
            }
        }
    }


  // verify result
	int success = 1;	
	for (int i=0; i<N; i++) {
		for (int j=0; j<MIN(M,K); j++) {
			if (A[i][j] != C[i][j]) {
				success = 0;
			}
		}
		for (int j=MIN(M,K); j<MAX(M,K); j++) {
			if (C[i][j] != 0) {
				success = 0;
			}
		}
	}


    // print verification result
    printf("Verification: %s\n", (success)?"OK":"ERR");

    freeMatrix(A);
    freeMatrix(B);
    freeMatrix(C);

    // Return success based on verification, but time is already printed
    return success ? EXIT_SUCCESS : EXIT_FAILURE;
}
