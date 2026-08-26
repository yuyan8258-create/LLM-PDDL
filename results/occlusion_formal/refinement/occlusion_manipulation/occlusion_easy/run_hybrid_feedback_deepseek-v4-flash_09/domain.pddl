(define (domain image_occlusion_manipulation)

  (:requirements
    :strips
    :typing
  )

  (:types
    brick
    location

    target-brick
    occluder-brick
      - brick

    structural-location
    temporary-location
    goal-location
      - location

    target-structural-location
    occluder-structural-location
      - structural-location
  )

  (:predicates

    ; A brick occupies a discrete planning location.
    (at
      ?b - brick
      ?loc - location
    )

    ; Benchmark abstraction:
    ; an upper occluder brick is structurally stacked directly
    ; on another occluder brick.
    (on
      ?upper - occluder-brick
      ?lower - occluder-brick
    )

    ; No movable structural brick is directly above this brick.
    (clear
      ?b - brick
    )

    ; Immediate active occlusion only.
    ;
    ; For stacked occluders in this benchmark, on(A,B) and
    ; occludes(A,B) are intentionally modelled together as an
    ; abstraction of the Lego-like structural dependency.
    ;
    ; This is a benchmark modelling assumption, not a general
    ; physical law that every object placed on another object
    ; necessarily occludes it.
    (occludes
      ?occ - occluder-brick
      ?blocked - brick
    )

    ; The brick is currently directly accessible with respect to
    ; the modelled occlusion chain.
    (accessible
      ?b - brick
    )

    ; The robot is currently holding this brick.
    (holding
      ?b - brick
    )

    ; The robot is not currently holding any brick.
    (handempty)

    ; A discrete location is currently unoccupied.
    (free
      ?loc - location
    )

    ; Phase flag.
    ; Becomes true only after the target has been placed in the
    ; goal location. Structural restoration actions require it.
    (target-relocated)
  )


  ; ============================================================
  ; 1. Remove an upper occluder from another occluder.
  ;
  ; This simultaneously removes the benchmark structural
  ; relation and its corresponding immediate occlusion relation,
  ; revealing exactly the next occluder in the chain.
  ; ============================================================

  (:action remove-stacked-occluder

    :parameters (
      ?occ - occluder-brick
      ?support - occluder-brick
    )

    :precondition
      (and
        (on ?occ ?support)
        (occludes ?occ ?support)
        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )

    :effect
      (and
        (not (on ?occ ?support))
        (not (occludes ?occ ?support))
        (not (clear ?occ))
        (not (accessible ?occ))
        (not (handempty))

        (holding ?occ)
        (clear ?support)
        (accessible ?support)
      )
  )


  ; ============================================================
  ; 2. Remove the front / ground-level occluder that directly
  ;    blocks the target.
  ;
  ; In Occlusion v1, this action can reveal only a target-brick.
  ; Occluder-to-occluder dependencies are handled exclusively by
  ; remove-stacked-occluder.
  ; ============================================================

  (:action remove-ground-occluder

    :parameters (
      ?occ - occluder-brick
      ?loc - occluder-structural-location
      ?revealed - target-brick
    )

    :precondition
      (and
        (at ?occ ?loc)
        (occludes ?occ ?revealed)
        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )

    :effect
      (and
        (not (at ?occ ?loc))
        (not (occludes ?occ ?revealed))
        (not (clear ?occ))
        (not (accessible ?occ))
        (not (handempty))

        (holding ?occ)
        (free ?loc)
        (accessible ?revealed)
      )
  )


  ; ============================================================
  ; 3. Put a removed occluder into a temporary location.
  ;
  ; This action cannot restore an occluder to a structural
  ; position because its destination type is temporary-location.
  ; ============================================================

  (:action put-down-occluder

    :parameters (
      ?occ - occluder-brick
      ?loc - temporary-location
    )

    :precondition
      (and
        (holding ?occ)
        (free ?loc)
      )

    :effect
      (and
        (not (holding ?occ))
        (not (free ?loc))

        (at ?occ ?loc)
        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )
  )


  ; ============================================================
  ; 4. Pick up an occluder from a temporary location.
  ;
  ; This is used for later restoration and cannot directly remove
  ; an active structural occluder.
  ; ============================================================

  (:action pick-up-temp-occluder

    :parameters (
      ?occ - occluder-brick
      ?loc - temporary-location
    )

    :precondition
      (and
        (at ?occ ?loc)
        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )

    :effect
      (and
        (not (at ?occ ?loc))
        (not (clear ?occ))
        (not (accessible ?occ))
        (not (handempty))

        (holding ?occ)
        (free ?loc)
      )
  )


  ; ============================================================
  ; 5. Pick up the target after the occlusion chain has been
  ;    correctly cleared.
  ; ============================================================

  (:action pick-up-target

    :parameters (
      ?target - target-brick
      ?loc - target-structural-location
    )

    :precondition
      (and
        (at ?target ?loc)
        (clear ?target)
        (accessible ?target)
        (handempty)
      )

    :effect
      (and
        (not (at ?target ?loc))
        (not (clear ?target))
        (not (accessible ?target))
        (not (handempty))

        (holding ?target)
        (free ?loc)
      )
  )


  ; ============================================================
  ; 6. Place the target in its goal location.
  ;
  ; This is the only action that enables the restoration phase.
  ; ============================================================

  (:action put-down-target

    :parameters (
      ?target - target-brick
      ?loc - goal-location
    )

    :precondition
      (and
        (holding ?target)
        (free ?loc)
      )

    :effect
      (and
        (not (holding ?target))
        (not (free ?loc))

        (at ?target ?loc)
        (clear ?target)
        (accessible ?target)
        (handempty)

        (target-relocated)
      )
  )


  ; ============================================================
  ; 7. Restore the front / ground-level occluder to its structural
  ;    location after the target has been relocated.
  ;
  ; Important:
  ; This action deliberately does NOT recreate the old
  ; occludes(O1,T1) relation. The target has already left the
  ; structure and is now in the goal region.
  ; ============================================================

  (:action restore-ground-occluder

    :parameters (
      ?occ - occluder-brick
      ?loc - occluder-structural-location
    )

    :precondition
      (and
        (holding ?occ)
        (free ?loc)
        (target-relocated)
      )

    :effect
      (and
        (not (holding ?occ))
        (not (free ?loc))

        (at ?occ ?loc)
        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )
  )


  ; ============================================================
  ; 8. Restore one stacked occluder layer.
  ;
  ; Restoration is available only after target relocation.
  ; In the benchmark abstraction, restoring an upper occluder on
  ; its support simultaneously restores both on(A,B) and the
  ; corresponding immediate occludes(A,B) relation.
  ; ============================================================

  (:action stack-occluder

    :parameters (
      ?occ - occluder-brick
      ?support - occluder-brick
    )

    :precondition
      (and
        (holding ?occ)
        (clear ?support)
        (accessible ?support)
        (target-relocated)
      )

    :effect
      (and
        (not (holding ?occ))
        (not (clear ?support))
        (not (accessible ?support))

        (on ?occ ?support)
        (occludes ?occ ?support)

        (clear ?occ)
        (accessible ?occ)
        (handempty)
      )
  )
)